from flowMC.sampler.HMC import HMC
from flowMC.utils.PRNG_keys import initialize_rng_keys
import jax
import jax.numpy as jnp
from jax.scipy.special import logsumexp


def dual_moon_pe(x, data):
    """
    Term 2 and 3 separate the distribution and smear it along the first and second dimension
    """
    print("compile count")
    term1 = 0.5 * ((jnp.linalg.norm(x - data) - 2) / 0.1) ** 2
    term2 = -0.5 * ((x[:1] + jnp.array([-3.0, 3.0])) / 0.8) ** 2
    term3 = -0.5 * ((x[1:2] + jnp.array([-3.0, 3.0])) / 0.6) ** 2
    return -(term1 - logsumexp(term2) - logsumexp(term3))


n_dim = 5
n_chains = 15
n_local_steps = 30
step_size = 0.1
n_leapfrog = 10

data = jnp.arange(5)

rng_key_set = initialize_rng_keys(n_chains, seed=42)

initial_position = jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1

HMC_sampler = HMC(
    dual_moon_pe,
    True,
    {
        "step_size": step_size,
        "n_leapfrog": n_leapfrog,
        "condition_matrix": jnp.eye(n_dim),
    },
)

initial_PE = HMC_sampler.logpdf_vmap(initial_position, data)

HMC_sampler.precompilation(n_chains, n_dim, n_local_steps, data)

initial_position = jnp.repeat(initial_position[:, None], n_local_steps, 1)
initial_PE = jnp.repeat(initial_PE[:, None], n_local_steps, 1)

state = (
    rng_key_set[1],
    initial_position,
    initial_PE,
    jnp.zeros((n_chains, n_local_steps, 1)),
    data,
)

HMC_sampler.update_vmap(1, state)

state = HMC_sampler.sample(rng_key_set[1], n_local_steps, initial_position[:, 0], data)


from flowMC.nfmodel.rqSpline import MaskedCouplingRQSpline
from flowMC.sampler.Sampler import Sampler

n_dim = 5
n_chains = 2
n_local_steps = 20
n_global_steps = 3
step_size = 0.1
n_loop_training = 2
n_loop_production = 2

rng_key_set = initialize_rng_keys(n_chains, seed=42)

initial_position = jax.random.normal(rng_key_set[0], shape=(n_chains, n_dim)) * 1

model = MaskedCouplingRQSpline(2, 4, [32, 32], 4, jax.random.PRNGKey(10))

print("Initializing sampler class")

nf_sampler = Sampler(
    n_dim,
    rng_key_set,
    jnp.arange(5),
    HMC_sampler,
    model,
    n_loop_training=n_loop_training,
    n_loop_production=n_loop_production,
    n_local_steps=n_local_steps,
    n_global_steps=n_global_steps,
    n_chains=n_chains,
    use_global=False,
)

nf_sampler.sample(initial_position, data)
