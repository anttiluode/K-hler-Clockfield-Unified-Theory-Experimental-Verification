"""
Experiment 1: Entropy Quantization — Atiyah-Singer Index Test
==============================================================
Prediction: Clockfield Gamma-shell entropy grows in discrete steps
(one complex zero mode per unit winding number, per Atiyah-Singer index theorem).
We place n isolated vortex cores, each with a localized frozen region,
and measure how total frozen area and entropy scale with n.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.ndimage import label, binary_fill_holes

TAU   = 1.5
XI    = 4 / np.pi   # freeze threshold ≈ 1.273
SIGMA = 0.4         # vortex core half-width
R_ENV = 1.5         # envelope radius (frozen region stays local)
GRID  = 300
L     = 16.0
DX    = L / GRID
A_PEAK = np.sqrt(XI / TAU) * 2.5   # peak amplitude → beta ≈ 2.5·Ξ at core


def gamma(beta):
    return 1.0 / (1.0 + TAU * beta) ** 2


def vortex_field(X, Y, cx, cy, winding=1):
    dx = X - cx
    dy = Y - cy
    r  = np.sqrt(dx**2 + dy**2 + 1e-9)
    th = np.arctan2(dy, dx)
    A  = A_PEAK * np.tanh(r / SIGMA) * np.exp(-r**2 / (2 * R_ENV**2))
    return A * np.exp(1j * winding * th)


def build_cluster(n_vortices, rng):
    x = np.linspace(-L/2, L/2, GRID)
    y = np.linspace(-L/2, L/2, GRID)
    X, Y = np.meshgrid(x, y)

    phi = np.zeros_like(X, dtype=complex)
    # Place vortices on a grid with enough separation (3·R_ENV)
    sep  = 3.0 * R_ENV
    side = max(1, int(np.ceil(np.sqrt(n_vortices))))
    for i in range(n_vortices):
        row = i // side
        col = i  % side
        cx  = -side*sep/2 + col*sep + sep/2 + rng.normal(0, 0.1)
        cy  = -side*sep/2 + row*sep + sep/2 + rng.normal(0, 0.1)
        # Clip to grid interior
        cx = np.clip(cx, -L/2 + R_ENV, L/2 - R_ENV)
        cy = np.clip(cy, -L/2 + R_ENV, L/2 - R_ENV)
        w  = +1 if i % 2 == 0 else -1
        phi += vortex_field(X, Y, cx, cy, winding=w)

    beta  = np.abs(phi) ** 2
    Gamma = gamma(beta)
    return phi, beta, Gamma, X, Y


def frozen_mask(Gamma):
    # Freeze threshold: Γ < Γ_freeze = 1/(1+τΞ)² ≈ 0.118, use 0.15
    return Gamma < 0.15


def compute_genus(mask):
    _, n_comp  = label(mask)
    filled     = binary_fill_holes(mask)
    holes      = filled & ~mask
    _, n_holes = label(holes)
    return max(0, n_holes), n_comp, n_holes


def topological_charge(phi):
    theta = np.angle(phi)
    dthx  = np.diff(theta, axis=1)
    dthy  = np.diff(theta, axis=0)
    dthx  = (dthx + np.pi) % (2*np.pi) - np.pi
    dthy  = (dthy + np.pi) % (2*np.pi) - np.pi
    curl  = np.diff(dthy, axis=1) - np.diff(dthx, axis=0)
    return np.sum(curl) / (2 * np.pi)


def run(n_trials=10, max_n=12, seed=42):
    rng = np.random.default_rng(seed)

    # Quick sanity check
    phi1, beta1, G1, _, _ = build_cluster(1, rng)
    ff = frozen_mask(G1).mean()
    print(f"Sanity: n=1  beta_max={beta1.max():.3f}  Gamma_min={G1.min():.4f}  "
          f"frozen_frac={ff:.4f} (want ~0.01–0.10)")
    rng = np.random.default_rng(seed)

    results = []
    for n_v in range(1, max_n + 1):
        tg, ta, tc, te = [], [], [], []
        for _ in range(n_trials):
            phi, beta, Gamma, _, _ = build_cluster(n_v, rng)
            mask   = frozen_mask(Gamma)
            area   = mask.sum() * DX**2
            g, _, _= compute_genus(mask)
            charge = abs(topological_charge(phi))
            S      = area / (4 * SIGMA**2)
            tg.append(g); ta.append(area); tc.append(charge); te.append(S)

        r = dict(n_v=n_v, genus=np.mean(tg), genus_std=np.std(tg),
                 area=np.mean(ta), area_std=np.std(ta),
                 charge=np.mean(tc), entropy=np.mean(te), entropy_std=np.std(te))
        results.append(r)
        print(f"n_v={n_v:2d}  g={r['genus']:.2f}±{r['genus_std']:.2f}"
              f"  area={r['area']:.3f}±{r['area_std']:.3f}"
              f"  S={r['entropy']:.3f}  |Q|={r['charge']:.2f}")
    return results


def analyse(results):
    n_v     = np.array([r['n_v']       for r in results])
    entropy = np.array([r['entropy']   for r in results])
    genus   = np.array([r['genus']     for r in results])
    area    = np.array([r['area']      for r in results])
    charge  = np.array([r['charge']    for r in results])
    ent_std = np.array([r['entropy_std'] for r in results])

    # Continuous fit
    def linear(x, a, b): return a*x + b
    try:
        popt, _ = curve_fit(linear, n_v.astype(float), entropy)
    except Exception:
        popt = [entropy[-1]/n_v[-1], 0.0]
    S_cont   = linear(n_v.astype(float), *popt)
    residual = entropy - S_cont

    # Atiyah-Singer: S_index = |Q| * log(2π)
    S_index = charge * np.log(2 * np.pi)

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle("Exp 1: Atiyah-Singer Entropy Quantization", fontsize=13)

    ax = axes[0, 0]
    ax.errorbar(n_v, entropy, yerr=ent_std, fmt='o-', color='steelblue',
                capsize=3, label='S_Bekenstein (sim)')
    ax.plot(n_v, S_cont,  'r--', alpha=0.7, label='Linear fit (continuous)')
    ax.plot(n_v, S_index, 's--', color='darkorange', alpha=0.8,
            label='S_index = |Q|·log(2π)')
    ax.set_xlabel('n_vortices'); ax.set_ylabel('Entropy S')
    ax.set_title('Entropy vs vortex count')
    ax.legend(fontsize=8); ax.grid(alpha=0.3)

    ax = axes[0, 1]
    cols = ['steelblue' if r >= 0 else 'crimson' for r in residual]
    ax.bar(n_v, residual, color=cols, alpha=0.8)
    ax.axhline(0, color='k', linewidth=0.8)
    ax.set_xlabel('n_vortices'); ax.set_ylabel('S − S_linear')
    ax.set_title('Residual after linear subtraction\n(oscillation = quantization signal)')
    ax.grid(alpha=0.3)

    ax = axes[1, 0]
    ax.errorbar(n_v, genus, yerr=[r['genus_std'] for r in results],
                fmt='o-', color='forestgreen', capsize=3, label='genus (sim)')
    # Theory: each vortex adds ~0.5 to genus (pairs form holes)
    ax.plot(n_v, n_v * 0.5, 'r--', alpha=0.6, label='g = 0.5·n (expected)')
    ax.set_xlabel('n_vortices'); ax.set_ylabel('Topological genus')
    ax.set_title('Genus growth'); ax.legend(fontsize=8); ax.grid(alpha=0.3)

    ax = axes[1, 1]
    rng_s = np.random.default_rng(7)
    phi_s, beta_s, Gamma_s, X, Y = build_cluster(4, rng_s)
    mask_s = frozen_mask(Gamma_s)
    im = ax.contourf(X, Y, Gamma_s, levels=25, cmap='plasma', vmin=0, vmax=1)
    ax.contour(X, Y, mask_s.astype(float), levels=[0.5], colors='white', linewidths=1.5)
    plt.colorbar(im, ax=ax, label='Γ(x)')
    ax.set_xlim(-6, 6); ax.set_ylim(-6, 6)
    ax.set_title('Γ field, n=4 vortices\n(white = frozen boundary)'); ax.set_xlabel('x')

    step_frac = np.var(residual) / (np.var(entropy) + 1e-12)
    verdict = (f"Step fraction: {100*step_frac:.1f}%  "
               f"({'SIGNIFICANT' if step_frac > 0.05 else 'weak'})\n"
               f"Linear fit: S = {popt[0]:.4f}·n + {popt[1]:.4f}")
    print("\n" + "="*55 + "\n" + verdict)
    fig.text(0.02, 0.005, verdict, fontsize=9, family='monospace', va='bottom')
    plt.tight_layout(rect=[0, 0.07, 1, 1])
    plt.savefig('exp1_entropy_quantization.png', dpi=150)
    print("Saved: exp1_entropy_quantization.png")
    plt.close()
if __name__ == "__main__":
    results = run(n_trials=10, max_n=12, seed=42)
    analyse(results)
