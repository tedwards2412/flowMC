from flowMC.sampler.HMC import HMC
from flowMC.sampler.MALA import MALA
from flowMC.sampler.Gaussian_random_walk import GaussianRandomWalk
from flowMC.sampler.NF_proposal import NFProposal
from flowMC.utils.PRNG_keys import initialize_rng_keys
import jax
import jax.numpy as jnp
from flowMC.nfmodel.rqSpline import MaskedCouplingRQSpline
from flowMC.nfmodel.utils import *
import optax  # Optimizers


def log_posterior(x, data=None):
    return -0.5 * jnp.sum(x**2)


class TestHMC:
    def test_HMC_deterministic(self):
        n_dim = 2
        n_chains = 1
        HMC_obj = HMC(
            log_posterior,
            True,
            {"step_size": 1, "n_leapfrog": 5, "condition_matrix": jnp.eye(n_dim)},
        )

        rng_key_set = initialize_rng_keys(n_chains, seed=42)

        initial_position = (
            jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1
        )
        initial_PE = jax.vmap(HMC_obj.potential)(initial_position, None)

        # Test whether the HMC kernel is deterministic

        result1 = HMC_obj.kernel(
            rng_key_set[0], initial_position[0], initial_PE[0], None
        )
        result2 = HMC_obj.kernel(
            rng_key_set[0], initial_position[0], initial_PE[0], None
        )

        assert jnp.allclose(result1[0], result2[0])
        assert result1[1] == result2[1]
        assert result1[2] == result2[2]

    def test_leapfrog_reversible(self):
        # Test whether the leapfrog kernel is reversible
        n_dim = 2
        n_chains = 1
        HMC_obj = HMC(
            log_posterior,
            True,
            {"step_size": 1, "n_leapfrog": 5, "condition_matrix": jnp.eye(n_dim)},
        )

        rng_key_set = initialize_rng_keys(n_chains, seed=42)
        initial_position = (
            jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1
        )
        initial_PE = jax.vmap(HMC_obj.potential, in_axes=(0, None))(
            initial_position, None
        )

        key1, key2 = jax.random.split(rng_key_set[0])

        initial_momentum = (
            jax.random.normal(key1, shape=initial_position.shape)
            * jnp.ones(n_dim) ** -0.5
        )
        new_position, new_momentum = HMC_obj.leapfrog_step(
            initial_position, initial_momentum, None, jnp.eye(n_dim)
        )
        rev_position, rev_momentum = HMC_obj.leapfrog_step(
            new_position, -new_momentum, None, jnp.eye(n_dim)
        )

        assert jnp.allclose(rev_position, initial_position)
        assert jnp.allclose(initial_PE, HMC_obj.potential(rev_position, None))

    def test_HMC_acceptance_rate(self):
        # Test acceptance rate goes to one when step size is small

        n_dim = 2
        HMC_obj = HMC(
            log_posterior,
            True,
            {"step_size": 0.0000001, "n_leapfrog": 5, "condition_matrix": jnp.eye(n_dim)},
        )

        n_chains = 100
        rng_key_set = initialize_rng_keys(n_chains, seed=42)

        initial_position = (
            jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1
        )
        initial_PE = - jax.vmap(HMC_obj.potential)(initial_position, None)

        result = HMC_obj.kernel_vmap(rng_key_set[1], initial_position, initial_PE, None)

        assert result[2].all()

    def test_HMC_close_gaussian(self):
        n_dim = 2
        n_chains = 1
        HMC_obj = HMC(
            log_posterior,
            True,
            {"step_size": 0.1, "n_leapfrog": 5, "condition_matrix": jnp.eye(n_dim)},
        )

        rng_key_set = initialize_rng_keys(n_chains, seed=42)

        initial_position = (
            jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1
        )
        HMC_obj.precompilation(n_chains, n_dim, 10000, None)

        result = HMC_obj.sample(rng_key_set[1], 10000, initial_position, None)

        assert jnp.isclose(jnp.mean(result[1]), 0, atol=3e-2) # sqrt(N) is the expected error, but we can get unlucky
        assert jnp.isclose(jnp.var(result[1]), 1, atol=3e-2)


class TestMALA:
    def test_MALA_deterministic(self):
        n_dim = 2
        n_chains = 1
        MALA_obj = MALA(log_posterior, True, {"step_size": 1})

        rng_key_set = initialize_rng_keys(n_chains, seed=42)

        initial_position = (
            jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1
        )
        initial_logp = log_posterior(initial_position, None)

        result1 = MALA_obj.kernel(
            rng_key_set[0], initial_position[0], initial_logp, None
        )
        result2 = MALA_obj.kernel(
            rng_key_set[0], initial_position[0], initial_logp, None
        )

        assert jnp.allclose(result1[0], result2[0])
        assert result1[1] == result2[1]
        assert result1[2] == result2[2]

    def test_MALA_acceptance_rate(self):
        # Test acceptance rate goes to one when the step size is small

        MALA_obj = MALA(log_posterior, True, {"step_size": 0.00001})

        n_chains = 100
        n_dim = 2
        rng_key_set = initialize_rng_keys(n_chains, seed=42)

        initial_position = (
            jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1
        )
        initial_logp = jax.vmap(log_posterior)(initial_position, None)

        result = MALA_obj.kernel_vmap(
            rng_key_set[1], initial_position, initial_logp, None
        )

        assert result[2].all()

    def test_MALA_close_gaussian(self):
        n_dim = 2
        n_chains = 1
        MALA_obj = MALA(log_posterior, True, {"step_size": 1})

        rng_key_set = initialize_rng_keys(n_chains, seed=42)

        initial_position = (
            jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1
        )
        MALA_obj.precompilation(n_chains, n_dim, 30000, None)

        result = MALA_obj.sample(rng_key_set[1], 30000, initial_position, None)

        assert jnp.isclose(jnp.mean(result[1]), 0, atol=1e-2)
        assert jnp.isclose(jnp.var(result[1]), 1, atol=1e-2)


class TestGRW:
    def test_Gaussian_random_walk_deterministic(self):
        n_dim = 2
        n_chains = 1
        GRW_obj = GaussianRandomWalk(log_posterior, True, {"step_size": 1})
        rng_key_set = initialize_rng_keys(n_chains, seed=42)

        initial_position = (
            jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1
        )
        initial_logp = log_posterior(initial_position)

        result1 = GRW_obj.kernel(
            rng_key_set[0], initial_position[0], initial_logp, None
        )
        result2 = GRW_obj.kernel(
            rng_key_set[0], initial_position[0], initial_logp, None
        )

        assert jnp.allclose(result1[0], result2[0])
        assert result1[1] == result2[1]
        assert result1[2] == result2[2]

    def test_Gaussian_random_walk_acceptance_rate(self):
        # Test acceptance rate goes to one when the step size is small

        n_dim = 2
        GRW_obj = GaussianRandomWalk(log_posterior, True, {"step_size": 0.00001})

        n_chains = 100
        rng_key_set = initialize_rng_keys(n_chains, seed=42)

        initial_position = (
            jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1
        )
        initial_logp = jax.vmap(log_posterior)(initial_position)

        result = GRW_obj.kernel_vmap(
            rng_key_set[1], initial_position, initial_logp, None
        )

        assert result[2].all()

    def test_Gaussian_random_walk_close_gaussian(self):
        n_dim = 2
        n_chains = 1
        GRW_obj = GaussianRandomWalk(log_posterior, True, {"step_size": 1})

        rng_key_set = initialize_rng_keys(n_chains, seed=42)

        initial_position = (
            jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1
        )
        GRW_obj.precompilation(n_chains, n_dim, 30000, None)

        result = GRW_obj.sample(rng_key_set[1], 30000, initial_position, None)

        assert jnp.isclose(jnp.mean(result[1]), 0, atol=3e-2)
        assert jnp.isclose(jnp.var(result[1]), 1, atol=3e-2)


class TestNF:
    def test_NF_kernel(self):

        key1, rng, init_rng = jax.random.split(jax.random.PRNGKey(0), 3)
        data = jax.random.normal(key1, (100, 2))

        num_epochs = 5
        batch_size = 100
        learning_rate = 0.001
        momentum = 0.9

        model = MaskedCouplingRQSpline(
            2,
            2,
            [16, 16],
            4,
            rng,
            data_mean=jnp.mean(data, axis=0),
            data_cov=jnp.cov(data.T),
        )
        optim = optax.adam(learning_rate, momentum)
        state = optim.init(eqx.filter(model, eqx.is_array))


        train_flow, train_epoch, train_step = make_training_loop(optim)
        rng, self.model, state, loss_values = train_flow(
            rng, model, data, state, num_epochs, batch_size, verbose=True
        )
        key1, rng, init_rng = jax.random.split(jax.random.PRNGKey(1), 3)

        n_dim = 2
        n_chains = 1
        NF_obj = NFProposal(log_posterior, True, self.model)

        initial_position = jax.random.normal(init_rng, shape=(n_chains, n_dim)) * 1
        samples = NF_obj.sample(rng, 100, initial_position, None)
