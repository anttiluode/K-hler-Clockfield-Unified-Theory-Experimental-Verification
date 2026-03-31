"""
Experiment 2: BPS Stability & Lepton Mass Hierarchy
====================================================
Tests the BPS bound prediction and what topological invariants
CAN and CANNOT reproduce the lepton mass hierarchy.

Honest ledger approach: report what the Burau representation gives,
compare to experiment, quantify the gap.
"""

import numpy as np
import matplotlib.pyplot as plt

TAU = 1.5
XI  = 4 / np.pi   # 1.2732
# BPS parameters
beta0  = XI / TAU   # field amplitude at freeze threshold
Gamma0 = 1.0 / (1.0 + TAU * beta0)**2
E_per_crossing = TAU * XI  # energy per braid crossing (natural units)

# ── Burau 2×2 reduced representation for B₃ ──────────────────────────────────
def burau2_s1(t): return np.array([[-t, 1], [0, 1]], dtype=complex)
def burau2_s2(t): return np.array([[1, 0], [t, -t]], dtype=complex)

def burau_matrix(word, t):
    s1=burau2_s1(t); s2=burau2_s2(t)
    s1i=np.linalg.inv(s1); s2i=np.linalg.inv(s2)
    M=np.eye(2,dtype=complex)
    for c in word:
        M = {'1':s1,'2':s2,'A':s1i,'B':s2i}[c] @ M
    return M

def alexander_polynomial(word, t):
    """Alexander polynomial at t: det(I - Burau(word, t))."""
    return np.linalg.det(np.eye(2) - burau_matrix(word, t))

# ── Lepton data ───────────────────────────────────────────────────────────────
LEPTONS = [
    dict(name='electron',  word='121',                     n_cross=3,  m_mev=0.511,   stable=True),
    dict(name='muon',      word='12121212',                n_cross=8,  m_mev=105.66,  stable=True),
    dict(name='tau',       word='1212121212121212',         n_cross=16, m_mev=1776.86, stable=True),
    dict(name='forbidden', word='1212121212121212'*2,       n_cross=32, m_mev=None,    stable=False),
]
m_exp = {l['name']: l['m_mev'] for l in LEPTONS if l['m_mev']}


def compute_bps():
    """
    For each lepton compute:
    1. Z-charge = n_crossings × E_per_crossing (topological central charge)
    2. BPS energy E_BPS = Z (saturated BPS)
    3. Topological invariants from Burau at several t values
    4. Check: does Z-charge ratio match experimental mass ratio?
    """
    results = []
    for lep in LEPTONS:
        n = lep['n_cross']
        word = lep['word']
        Z = n * E_per_crossing

        # Alexander polynomial at t = -1 (standard)
        alex = alexander_polynomial(word, -1.0)

        # Burau trace at several t for diagnostic
        traces = {}
        for t_label, t in [('t=-1', -1.0), ('t=i', 1j), ('t=0.5', 0.5)]:
            M = burau_matrix(word, t)
            traces[t_label] = abs(np.trace(M))

        results.append(dict(
            name=lep['name'],
            n_cross=n,
            Z=Z,
            alex_t_neg1=abs(alex),
            traces=traces,
            stable=lep['stable'],
            m_exp=lep['m_mev'],
        ))
    return results


def power_law_fit(n_vals, m_vals):
    """Fit log(m) = α·log(n) + c."""
    log_n = np.log(n_vals)
    log_m = np.log(m_vals)
    alpha, c = np.polyfit(log_n, log_m, 1)
    return alpha, np.exp(c)


def run():
    print("="*60)
    print("Experiment 2: BPS Stability & Lepton Mass Hierarchy")
    print("="*60)
    print(f"\nKähler parameters: τ={TAU}, Ξ={XI:.4f}")
    print(f"Gamma₀={Gamma0:.4f}, E_per_crossing={E_per_crossing:.4f}\n")

    results = compute_bps()

    print(f"{'Lepton':<12} {'n_cross':<10} {'Z-charge':<12} {'|Alex(t=-1)|':<15} {'Status'}")
    print("-"*60)
    for r in results:
        status = "stable" if r['stable'] else "FORBIDDEN"
        print(f"{r['name']:<12} {r['n_cross']:<10} {r['Z']:<12.4f} "
              f"{r['alex_t_neg1']:<15.4f} {status}")

    # Mass ratio analysis
    stable = [r for r in results if r['stable'] and r['m_exp']]
    n_vals  = np.array([r['n_cross'] for r in stable])
    m_vals  = np.array([r['m_exp']   for r in stable])
    Z_vals  = np.array([r['Z']       for r in stable])

    alpha_n, c_n = power_law_fit(n_vals, m_vals)
    alpha_Z, c_Z = power_law_fit(Z_vals, m_vals)

    print(f"\n── Power law fits ──")
    print(f"log(m) = α·log(n_cross) + c:  α={alpha_n:.3f}  (need α≈{np.log(1776.86/0.511)/np.log(16/3):.2f} for exact)")
    print(f"log(m) = α·log(Z) + c:         α={alpha_Z:.3f}")

    print(f"\n── Mass ratio predictions (Z-charge model) ──")
    Z_e = Z_vals[0]
    for r in stable[1:]:
        r_sim = r['Z'] / Z_e
        r_exp = r['m_exp'] / stable[0]['m_exp']
        err   = abs(r_sim - r_exp) / r_exp * 100
        print(f"  m_{r['name']}/m_electron: Z_ratio={r_sim:.2f}  exp={r_exp:.1f}  err={err:.1f}%")

    # What power of n would give the right ratios?
    print(f"\n── What α in m ∝ n^α fits experiment? ──")
    r_muon = m_exp['muon'] / m_exp['electron']
    r_tau  = m_exp['tau']  / m_exp['electron']
    alpha_from_muon = np.log(r_muon) / np.log(8.0/3.0)
    alpha_from_tau  = np.log(r_tau)  / np.log(16.0/3.0)
    print(f"  From muon ratio:  α = {alpha_from_muon:.3f}")
    print(f"  From tau  ratio:  α = {alpha_from_tau:.3f}")
    print(f"  → These don't agree ({alpha_from_muon:.2f} ≠ {alpha_from_tau:.2f})")
    print(f"  → Pure crossing-number power law CANNOT reproduce hierarchy.")
    print(f"  → The 8% tau mass paper result uses a specific braid word,")
    print(f"     not the simple (σ1σ2)^n family.")

    # ── Plot ─────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    fig.suptitle("Exp 2: BPS Stability & Lepton Mass Hierarchy", fontsize=13)

    ax = axes[0]
    names   = [r['name']   for r in stable]
    Z_ratio = Z_vals / Z_vals[0]
    m_ratio = m_vals / m_vals[0]
    colors  = ['royalblue', 'forestgreen', 'darkorange']
    ax.loglog(Z_ratio, m_ratio, 'o', color='steelblue', ms=10)
    ax.loglog(Z_ratio, Z_ratio, 'r--', alpha=0.6, label='BPS: m∝Z (α=1)')
    # Best fit
    m_fit = c_Z * Z_vals**alpha_Z
    ax.loglog(Z_ratio, m_fit/m_fit[0], 'g-.', alpha=0.8,
              label=f'Best fit α={alpha_Z:.2f}')
    for i, n in enumerate(names):
        ax.annotate(n, (Z_ratio[i], m_ratio[i]), xytext=(6,4),
                    textcoords='offset points', fontsize=9)
    ax.set_xlabel('Z-charge ratio'); ax.set_ylabel('Mass ratio (rel. to electron)')
    ax.set_title('BPS prediction vs experiment\n(on red line = BPS confirmed)')
    ax.legend(fontsize=8); ax.grid(alpha=0.3, which='both')

    ax = axes[1]
    # Crossing number vs mass
    n_all = np.array([r['n_cross'] for r in stable])
    ax.loglog(n_all/n_all[0], m_ratio, 'o-', color='steelblue', ms=10)
    # Several power laws
    for alpha_test, col, lab in [(1,'gray','α=1'), (alpha_n,'darkorange',f'fit α={alpha_n:.2f}'),
                                  (4,'crimson','α=4')]:
        y = (n_all/n_all[0])**alpha_test
        ax.loglog(n_all/n_all[0], y, '--', color=col, alpha=0.7, label=lab)
    for i, n in enumerate(names):
        ax.annotate(n, (n_all[i]/n_all[0], m_ratio[i]), xytext=(6,4),
                    textcoords='offset points', fontsize=9)
    ax.set_xlabel('Crossing number ratio'); ax.set_ylabel('Mass ratio')
    ax.set_title('m vs n_crossings power law\n(what α fits?)')
    ax.legend(fontsize=8); ax.grid(alpha=0.3, which='both')

    ax = axes[2]
    # Alexander polynomial values
    alex_vals = np.array([r['alex_t_neg1'] for r in stable])
    ax.bar(names, alex_vals, color=colors, alpha=0.8)
    ax.set_ylabel('|Alexander polynomial at t=-1|')
    ax.set_title('Burau topological invariant\n(saturated → same = BPS-like)')
    ax.grid(alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig('exp2_bps_leptons.png', dpi=150)
    print("\nSaved: exp2_bps_leptons.png")
    plt.close()


if __name__ == '__main__':
    run()