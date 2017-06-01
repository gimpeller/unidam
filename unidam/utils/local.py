import numpy as np
from scipy.stats import norm, truncnorm
from unidam.skewnorm_boosted import skewnorm_boosted as skewnorm
from unidam.utils.trunc_t import trunc_t
from unidam.utils.trunc_revexpon import trunc_revexpon


def get_param(fit, par):
    """
    Convert parameters from DB to distribution parameters.
    """
    if fit == 'S':
        return skewnorm, [par[2], par[0], par[1]]
    elif fit == 'G':
        return norm, [par[0], par[1]]
    elif fit == 'T':
        sigma = np.abs(par[1])
        alpha = (par[2] - par[0]) / par[1]
        beta = (par[3] - par[0]) / par[1]
        return truncnorm, [alpha, beta, par[0], sigma]
    elif fit == 'P':
        sigma = np.abs(par[1])
        alpha = (par[3] - par[0]) / par[1]
        beta = (par[4] - par[0]) / par[1]
        return trunc_t, [par[2], alpha, beta, par[0], sigma]
    elif fit == 'L':
        sigma = np.abs(par[1])
        if par[0] < par[2]:
            par[0] = par[2] - 1e-3
        elif par[0] > par[3]:
            par[0] = par[3] + 1e-3
        alpha = (par[2] - par[0]) / sigma
        beta = (par[3] - par[0]) / sigma
        return trunc_revexpon, [alpha, beta, par[0], sigma]
    else:
        raise ValueError('Unknown fit type: %s' % fit)
    return None
