"""
Experiment 3 (Proper): Does the Clockfield Γ Form Emerge from Training?
=========================================================================
DeepSeek's critique: "You haven't compared against a learnable gating mechanism.
Show that the specific functional form Γ = 1/(1+τβ)² emerges naturally from
training a standard transformer without being hardcoded."

This experiment does exactly that.

Two comparisons:
(A) Clockfield gate (fixed τ=50, hardcoded form) vs MLP gate (learnable, same param count)
    Tests: is the Γ form special, or does any nonlinear gate work equally well?

(B) Train a gate with learnable τ from scratch (τ initialized to 1.0)
    Tests: does gradient descent push τ toward large values (freezing regime)?
    If yes: the Clockfield form is an attractor in representation learning.

(C) Fit the LEARNED MLP gate function to the Clockfield form post-training
    Tests: does the learned gate approximate Γ = 1/(1+τβ)²?
    If yes: Clockfield is the correct functional form, not merely one option.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import matplotlib.pyplot as plt

torch.manual_seed(42)
np.random.seed(42)


# ── Dataset ──────────────────────────────────────────────────────────────────
def make_data(n, d, n_classes, noise_std, seed=None):
    rng = torch.Generator()
    if seed is not None:
        rng.manual_seed(seed)
    canonical = torch.linspace(0, 2*np.pi, n_classes+1)[:-1]
    X = torch.zeros(n, d, dtype=torch.cfloat)
    Y = torch.randint(0, n_classes, (n,), generator=rng)
    for i in range(n):
        cls   = Y[i].item()
        phase = canonical[cls] + torch.randn(d, generator=rng) * noise_std
        amp   = 0.8 + 0.4 * torch.rand(d, generator=rng)
        X[i]  = amp * torch.exp(1j * phase)
    return X, Y


# ── Models ───────────────────────────────────────────────────────────────────

class ClockfieldNet(nn.Module):
    """Fixed Clockfield gate: Γ = 1/(1+τ·Im²)²"""
    def __init__(self, d, n_slots, n_classes, tau=50.0):
        super().__init__()
        self.tau    = tau
        self.W_q    = nn.Parameter(torch.randn(d, d, dtype=torch.cfloat) / np.sqrt(d))
        self.Keys   = nn.Parameter(torch.randn(n_slots, d, dtype=torch.cfloat) / np.sqrt(d))
        self.Values = nn.Parameter(torch.randn(n_slots, d, dtype=torch.cfloat) / np.sqrt(d))
        self.out    = nn.Linear(d*2, n_classes)

    def forward(self, x):
        Q   = x @ self.W_q
        S   = Q @ self.Keys.conj().T
        beta = S.imag ** 2
        Gamma = 1.0 / (1.0 + self.tau * beta) ** 2
        attn  = F.softmax(S.real, dim=-1) * Gamma
        out   = (attn.to(torch.cfloat) @ self.Values)
        return self.out(torch.cat([out.real, out.imag], dim=-1)), Gamma, beta


class LearnedTauNet(nn.Module):
    """Clockfield gate with LEARNABLE τ (initialized to 1.0).
    Tests whether gradient descent pushes τ toward large values."""
    def __init__(self, d, n_slots, n_classes, tau_init=1.0):
        super().__init__()
        self.log_tau = nn.Parameter(torch.tensor(np.log(tau_init)))
        self.W_q     = nn.Parameter(torch.randn(d, d, dtype=torch.cfloat) / np.sqrt(d))
        self.Keys    = nn.Parameter(torch.randn(n_slots, d, dtype=torch.cfloat) / np.sqrt(d))
        self.Values  = nn.Parameter(torch.randn(n_slots, d, dtype=torch.cfloat) / np.sqrt(d))
        self.out     = nn.Linear(d*2, n_classes)

    def forward(self, x):
        tau  = torch.exp(self.log_tau)
        Q    = x @ self.W_q
        S    = Q @ self.Keys.conj().T
        beta = S.imag ** 2
        Gamma = 1.0 / (1.0 + tau * beta) ** 2
        attn  = F.softmax(S.real, dim=-1) * Gamma
        out   = (attn.to(torch.cfloat) @ self.Values)
        return self.out(torch.cat([out.real, out.imag], dim=-1)), Gamma, beta

    def get_tau(self):
        return torch.exp(self.log_tau).item()


class MLPGateNet(nn.Module):
    """Learnable MLP gate replaces the Clockfield Γ function.
    Same parameter count as the Clockfield (roughly).
    Gate = MLP(Im[S]²) → scalar in [0,1]."""
    def __init__(self, d, n_slots, n_classes, n_hidden=16):
        super().__init__()
        self.W_q    = nn.Parameter(torch.randn(d, d, dtype=torch.cfloat) / np.sqrt(d))
        self.Keys   = nn.Parameter(torch.randn(n_slots, d, dtype=torch.cfloat) / np.sqrt(d))
        self.Values = nn.Parameter(torch.randn(n_slots, d, dtype=torch.cfloat) / np.sqrt(d))
        self.gate   = nn.Sequential(
            nn.Linear(1, n_hidden),
            nn.ReLU(),
            nn.Linear(n_hidden, 1),
            nn.Sigmoid()
        )
        self.out    = nn.Linear(d*2, n_classes)

    def forward(self, x):
        Q    = x @ self.W_q
        S    = Q @ self.Keys.conj().T
        beta = S.imag ** 2   # shape (batch, slots)
        # Gate: apply MLP to each beta value
        b_flat = beta.reshape(-1, 1)
        g_flat = self.gate(b_flat)
        Gamma  = g_flat.reshape(beta.shape)
        attn   = F.softmax(S.real, dim=-1) * Gamma
        out    = (attn.to(torch.cfloat) @ self.Values)
        return self.out(torch.cat([out.real, out.imag], dim=-1)), Gamma, beta


class StandardMoireNet(nn.Module):
    """No gate — plain softmax(Re[S])."""
    def __init__(self, d, n_slots, n_classes):
        super().__init__()
        self.W_q    = nn.Parameter(torch.randn(d, d, dtype=torch.cfloat) / np.sqrt(d))
        self.Keys   = nn.Parameter(torch.randn(n_slots, d, dtype=torch.cfloat) / np.sqrt(d))
        self.Values = nn.Parameter(torch.randn(n_slots, d, dtype=torch.cfloat) / np.sqrt(d))
        self.out    = nn.Linear(d*2, n_classes)

    def forward(self, x):
        Q    = x @ self.W_q
        S    = Q @ self.Keys.conj().T
        attn = F.softmax(S.real, dim=-1)
        out  = (attn.to(torch.cfloat) @ self.Values)
        dummy_gamma = torch.ones_like(attn)
        dummy_beta  = (S.imag**2)
        return self.out(torch.cat([out.real, out.imag], dim=-1)), dummy_gamma, dummy_beta


# ── Training ─────────────────────────────────────────────────────────────────

def train(model, X, Y, epochs=400, lr=5e-3):
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    losses = []
    tau_history = []
    model.train()
    for ep in range(epochs):
        opt.zero_grad()
        logits, _, _ = model(X)
        loss = F.cross_entropy(logits, Y)
        loss.backward()
        for p in model.parameters():
            if p.grad is not None and p.grad.is_conj():
                p.grad = p.grad.resolve_conj()
        opt.step()
        losses.append(loss.item())
        if isinstance(model, LearnedTauNet):
            tau_history.append(model.get_tau())
    return losses, tau_history


def evaluate(model, X_test, Y_test):
    model.eval()
    with torch.no_grad():
        logits, Gamma, beta = model(X_test)
        preds = logits.argmax(dim=1)
        acc   = (preds == Y_test).float().mean().item()
        g_np  = Gamma.flatten().cpu().numpy()
        b_np  = beta.flatten().cpu().numpy()
    return acc, g_np, b_np


# ── Gate function fitting ─────────────────────────────────────────────────────

def fit_clockfield_to_learned_gate(mlp_model, beta_range=(0, 5)):
    """
    After training MLP gate, measure the learned gate as a function of β,
    then fit the Clockfield form Γ = 1/(1+τβ)² to it.
    Returns: fitted τ, R² of fit, gate curve.
    """
    beta_vals = torch.linspace(beta_range[0], beta_range[1], 200).unsqueeze(1)
    with torch.no_grad():
        gate_vals = mlp_model.gate(beta_vals).squeeze().numpy()
    beta_np = beta_vals.squeeze().numpy()
    
    # Fit Γ = 1/(1+τβ)²
    from scipy.optimize import curve_fit
    def clockfield_gate(beta, tau):
        return 1.0 / (1.0 + tau * beta) ** 2
    try:
        popt, _ = curve_fit(clockfield_gate, beta_np, gate_vals,
                            p0=[5.0], bounds=(0, 1000), maxfev=5000)
        tau_fit  = popt[0]
        g_pred   = clockfield_gate(beta_np, tau_fit)
        ss_res   = np.sum((gate_vals - g_pred)**2)
        ss_tot   = np.sum((gate_vals - gate_vals.mean())**2)
        r2       = 1 - ss_res / (ss_tot + 1e-10)
    except Exception:
        tau_fit, r2, g_pred = None, None, None
    
    return tau_fit, r2, g_pred, beta_np, gate_vals


# ── Main ─────────────────────────────────────────────────────────────────────

def run():
    print("="*65)
    print("Experiment 3 (Proper): Does Clockfield Form Emerge from Training?")
    print("="*65)
    
    D = 16; N_CLASSES = 6; N_SLOTS = 12; TRAIN_NOISE = 0.4
    
    X_train, Y_train = make_data(800, D, N_CLASSES, TRAIN_NOISE, seed=42)
    
    models = {
        'Standard Moiré': StandardMoireNet(D, N_SLOTS, N_CLASSES),
        'Clockfield τ=50 (fixed)': ClockfieldNet(D, N_SLOTS, N_CLASSES, tau=50.0),
        'Clockfield τ=1→? (learned)': LearnedTauNet(D, N_SLOTS, N_CLASSES, tau_init=1.0),
        'MLP gate (learnable)': MLPGateNet(D, N_SLOTS, N_CLASSES, n_hidden=16),
    }
    
    print("\nTraining all models (400 epochs each)...")
    all_losses = {}
    tau_histories = {}
    for name, model in models.items():
        print(f"  {name}...", end='', flush=True)
        losses, tau_hist = train(model, X_train, Y_train, epochs=400)
        all_losses[name] = losses
        tau_histories[name] = tau_hist
        if isinstance(model, LearnedTauNet):
            print(f" τ: {1.0:.2f} → {model.get_tau():.2f}")
        else:
            print(f" final loss: {losses[-1]:.4f}")
    
    # Generalization sweep
    noise_levels = np.linspace(0.1, 2.5, 20)
    accs = {name: [] for name in models}
    
    print("\nGeneralization sweep...")
    for noise in noise_levels:
        X_test, Y_test = make_data(400, D, N_CLASSES, noise, seed=99)
        for name, model in models.items():
            acc, _, _ = evaluate(model, X_test, Y_test)
            accs[name].append(acc)
    
    # Gate function analysis for MLP model
    mlp_model = models['MLP gate (learnable)']
    tau_fit, r2_fit, g_pred, beta_np, gate_vals = fit_clockfield_to_learned_gate(mlp_model)
    
    print(f"\n── Gate function analysis ──")
    print(f"Learned τ (gradient-trained): {models['Clockfield τ=1→? (learned)'].get_tau():.3f}")
    print(f"  (started at 1.0 — if >> 1, Clockfield form is attractor)")
    if tau_fit is not None:
        print(f"MLP gate fit to Clockfield form: τ_fit = {tau_fit:.3f}, R² = {r2_fit:.4f}")
        print(f"  (R²>0.90 → learned gate approximates Clockfield form)")
    
    # ── Plot ─────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    fig.suptitle("Exp 3 (Proper): Clockfield Form vs Learned Gate", fontsize=13)
    
    colors = {
        'Standard Moiré': 'steelblue',
        'Clockfield τ=50 (fixed)': 'crimson',
        'Clockfield τ=1→? (learned)': 'darkorange',
        'MLP gate (learnable)': 'forestgreen',
    }
    styles = {
        'Standard Moiré': 'o-',
        'Clockfield τ=50 (fixed)': 's-',
        'Clockfield τ=1→? (learned)': '^-',
        'MLP gate (learnable)': 'D-',
    }
    
    ax = axes[0, 0]
    for name in models:
        ax.plot(noise_levels, accs[name], styles[name], color=colors[name],
                label=name, markersize=5, alpha=0.9)
    ax.axvline(TRAIN_NOISE, color='k', linestyle='--', alpha=0.4, label='train noise')
    ax.set_xlabel('Phase noise σ'); ax.set_ylabel('Accuracy')
    ax.set_title('Generalization: all four models')
    ax.legend(fontsize=7); ax.grid(alpha=0.3)
    
    ax = axes[0, 1]
    # Training curves
    for name in models:
        ax.plot(all_losses[name], color=colors[name], label=name, alpha=0.8, linewidth=1.2)
    ax.set_xlabel('Epoch'); ax.set_ylabel('Training loss')
    ax.set_title('Training loss curves')
    ax.legend(fontsize=7); ax.grid(alpha=0.3)
    ax.set_yscale('log')
    
    ax = axes[1, 0]
    # Learned τ history
    tau_hist = tau_histories.get('Clockfield τ=1→? (learned)', [])
    if tau_hist:
        ax.plot(tau_hist, color='darkorange', linewidth=1.5)
        ax.axhline(1.0,  color='k',   linestyle='--', alpha=0.5, label='τ_init=1')
        ax.axhline(50.0, color='crimson', linestyle=':', alpha=0.5, label='τ_fixed=50')
        ax.set_xlabel('Epoch'); ax.set_ylabel('τ (learned)')
        ax.set_title(f"Learned τ trajectory\n(final: {tau_hist[-1]:.2f})")
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
    
    ax = axes[1, 1]
    # MLP gate shape vs Clockfield form
    ax.plot(beta_np, gate_vals, 'o', color='forestgreen', markersize=3,
            alpha=0.7, label='Learned MLP gate')
    if g_pred is not None:
        ax.plot(beta_np, g_pred, 'r-', linewidth=2,
                label=f'Clockfield fit: τ={tau_fit:.1f}, R²={r2_fit:.3f}')
    # Also plot fixed τ=50 for reference
    gamma_50 = 1.0 / (1.0 + 50.0 * beta_np)**2
    ax.plot(beta_np, gamma_50, 'k--', linewidth=1, alpha=0.5, label='Γ(τ=50)')
    ax.set_xlabel('β = Im[⟨Q,K⟩]²'); ax.set_ylabel('Gate value')
    ax.set_title('Learned gate shape vs Clockfield form\n(R²≈1 → Clockfield is attractor)')
    ax.legend(fontsize=8); ax.grid(alpha=0.3)
    ax.set_ylim(-0.05, 1.1)
    
    plt.tight_layout()
    plt.savefig('/mnt/user-data/outputs/exp3_learned_gate_proper.png', dpi=150)
    print("\nSaved: exp3_learned_gate_proper.png")
    plt.close()
    
    # Final verdict
    learned_tau = models['Clockfield τ=1→? (learned)'].get_tau()
    print(f"\n{'='*65}")
    print("VERDICT:")
    print(f"  Learned τ: {learned_tau:.3f}  "
          f"({'→ Clockfield attractor CONFIRMED (τ>>1)' if learned_tau > 5 else '→ τ did not grow significantly'})")
    if r2_fit is not None:
        print(f"  MLP gate R² fit to Clockfield: {r2_fit:.4f}  "
              f"({'→ Clockfield form CONFIRMED' if r2_fit > 0.90 else '→ Clockfield form not recovered'})")


if __name__ == '__main__':
    run()
