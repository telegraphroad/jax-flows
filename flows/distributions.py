import jax.numpy as np
from jax import random
from jax.scipy.special import logsumexp
from jax.scipy.stats import norm, multivariate_normal
import tensorflow_probability as tfp 
from jax.config import config
config.update("jax_enable_x64", True)

tfp = tfp.substrates.jax
tfd = tfp.distributions


def Normal(loc=0.,scale=1.):
    """
    Returns:
        A function mapping ``(rng, input_dim)`` to a ``(params, log_pdf, sample)`` triplet.
    """
    dist = tfd.Normal(loc=loc, scale=scale)
    def init_fun(rng, input_dim):
        def log_pdf(params, inputs):
            return dist.log_prob(inputs).sum(1)

        def sample(rng, params, num_samples=1):
            return dist.sample((num_samples, input_dim), rng)

        return (), log_pdf, sample

    return init_fun



def GenNormal(loc=0.,scale=1.,power=2.):
    """
    Returns:
        A function mapping ``(rng, input_dim)`` to a ``(params, log_pdf, sample)`` triplet.
    """

    def init_fun(rng, input_dim):
        dist = tfd.GeneralizedNormal(loc=loc, scale=scale, power=power)
        
        def log_pdf(params, inputs):
            return dist.log_prob(inputs).sum(1)

        def sample(rng, params, num_samples=1):
            return dist.sample((num_samples, input_dim), rng)

        return (), log_pdf, sample

    return init_fun


def GMM(means, covariances, weights):
    def init_fun(rng, input_dim):
        def log_pdf(params, inputs):
            cluster_lls = []
            for log_weight, mean, cov in zip(np.log(weights), means, covariances):
                cluster_lls.append(log_weight + multivariate_normal.logpdf(inputs, mean, cov))
            return logsumexp(np.vstack(cluster_lls), axis=0)

        def sample(rng, params, num_samples=1):
            cluster_samples = []
            for mean, cov in zip(means, covariances):
                rng, temp_rng = random.split(rng)
                cluster_sample = random.multivariate_normal(temp_rng, mean, cov, (num_samples,))
                cluster_samples.append(cluster_sample)
            samples = np.dstack(cluster_samples)
            idx = random.categorical(rng, weights, shape=(num_samples, 1, 1))
            return np.squeeze(np.take_along_axis(samples, idx, -1))

        return (), log_pdf, sample

    return init_fun


def Flow(transformation, prior=Normal()):
    """
    Args:
        transformation: a function mapping ``(rng, input_dim)`` to a
            ``(params, direct_fun, inverse_fun)`` triplet
        prior: a function mapping ``(rng, input_dim)`` to a
            ``(params, log_pdf, sample)`` triplet

    Returns:
        A function mapping ``(rng, input_dim)`` to a ``(params, log_pdf, sample)`` triplet.

    Examples:
        >>> import flows
        >>> input_dim, rng = 3, random.PRNGKey(0)
        >>> transformation = flows.Serial(
        ...     flows.Reverse(),
        ...     flows.Reverse()
        ... )
        >>> init_fun = flows.Flow(transformation, Normal())
        >>> params, log_pdf, sample = init_fun(rng, input_dim)
    """

    def init_fun(rng, input_dim):
        transformation_rng, prior_rng = random.split(rng)

        params, direct_fun, inverse_fun = transformation(transformation_rng, input_dim)
        prior_params, prior_log_pdf, prior_sample = prior(prior_rng, input_dim)

        def log_pdf(params, inputs):
            u, log_det = direct_fun(params, inputs)
            log_probs = prior_log_pdf(prior_params, u)
            return log_probs + log_det

        def sample(rng, params, num_samples=1):
            prior_samples = prior_sample(rng, prior_params, num_samples)
            return inverse_fun(params, prior_samples)[0]

        return params, log_pdf, sample

    return init_fun
