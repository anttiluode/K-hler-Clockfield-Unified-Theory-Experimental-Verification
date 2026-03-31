"""
Experiment 3: The True Topological Phase Transition
============================================================
Forcing the neural network to obey the Clockfield geometry by 
applying a massive coupling constant (τ = 50.0). This bridges the 
scale gap between PyTorch's tiny internal activations and the 
physical threshold needed to trigger a bimodal freeze (Γ -> 0).
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import numpy as np
import matplotlib.pyplot as plt

torch.manual_seed(42)
np.random.seed(42)

# ── 1. Dataset Generation ─────────────────────────────────────────────────────

def generate_phase_data(n_samples, d, n_classes, noise_std):
    class_phases = torch.linspace(0, 2*np.pi, n_classes+1)[:-1]
    X = torch.zeros(n_samples, d, dtype=torch.cfloat)
    Y = torch.randint(0, n_classes, (n_samples,))

    for i in range(n_samples):
        cls = Y[i]
        phase = class_phases[cls] + torch.randn(d) * noise_std
        amp = 0.8 + 0.4 * torch.rand(d)
        X[i] = amp * torch.exp(1j * phase)
    return X, Y

# ── 2. The Model: Hardcoded Clockfield Attention ──────────────────────────────

class ClockfieldAttentionNet(nn.Module):
    def __init__(self, d, num_slots, n_classes, use_clockfield=False):
        super().__init__()
        
        self.use_clockfield = use_clockfield
        
        # The critical fix: Force a massive tau to bridge the scale gap
        # between PyTorch's 1/sqrt(d) scaling and the physical threshold
        self.tau = 50.0 if use_clockfield else 0.0 
            
        self.W_q = nn.Parameter(torch.randn(d, d, dtype=torch.cfloat) / np.sqrt(d))
        self.Keys = nn.Parameter(torch.randn(num_slots, d, dtype=torch.cfloat) / np.sqrt(d))
        self.Values = nn.Parameter(torch.randn(num_slots, d, dtype=torch.cfloat) / np.sqrt(d))
        self.classifier = nn.Linear(d * 2, n_classes)

    def forward(self, x):
        Q = x @ self.W_q  
        S = Q @ self.Keys.conj().resolve_conj().T 
        
        attn_base = F.softmax(S.real, dim=-1)
        
        if self.use_clockfield:
            # Physical topological routing enabled
            beta = (S.imag) ** 2                      
            gamma = 1.0 / (1.0 + self.tau * beta)**2  
            attn_weights = attn_base * gamma 
        else:
            # Standard neural network (Thawed)
            attn_weights = attn_base
            gamma = torch.ones_like(attn_base)
            
        out = attn_weights.to(torch.cfloat) @ self.Values  
        out_cat = torch.cat([out.real, out.imag], dim=-1)
        logits = self.classifier(out_cat)
        
        return logits, gamma

# ── 3. Training Routine ───────────────────────────────────────────────────────

def train_model(model, X_train, Y_train, epochs=300, lr=0.01):
    optimizer = optim.Adam(model.parameters(), lr=lr)
    model.train()
    
    for epoch in range(epochs):
        optimizer.zero_grad()
        logits, _ = model(X_train)
        loss = F.cross_entropy(logits, Y_train) 
        loss.backward()
        
        # PyTorch complex gradient boilerplate
        for p in model.parameters():
            if p.grad is not None and p.grad.is_conj():
                p.grad = p.grad.resolve_conj()
                
        optimizer.step()

def evaluate_model(model, X_test, Y_test):
    model.eval()
    with torch.no_grad():
        logits, gamma = model(X_test)
        preds = torch.argmax(logits, dim=1)
        acc = (preds == Y_test).float().mean().item()
        
        # Return ALL gamma values for the histogram
        gamma_vals = gamma.flatten().cpu().numpy()
    return acc, gamma_vals

# ── 4. Main Experiment ────────────────────────────────────────────────────────

def run():
    print("="*65)
    print("Experiment 3: Forced Topological Phase Transition")
    print("="*65)

    D = 16            
    N_CLASSES = 6     
    N_SLOTS = 12      
    TRAIN_NOISE = 0.4 

    print(f"Generating training data (N=800, Noise={TRAIN_NOISE})...")
    X_train, Y_train = generate_phase_data(800, D, N_CLASSES, TRAIN_NOISE)

    model_moire = ClockfieldAttentionNet(D, N_SLOTS, N_CLASSES, use_clockfield=False)
    model_clock = ClockfieldAttentionNet(D, N_SLOTS, N_CLASSES, use_clockfield=True) 
    
    print("\nTraining Standard Moiré Model (τ = 0.0)...")
    train_model(model_moire, X_train, Y_train)

    print("Training Clockfield Model (Hardcoded τ = 50.0)...")
    train_model(model_clock, X_train, Y_train)
    
    # ── 5. Generalization Sweep ───────────────────────────────────────────────
    print("\nEvaluating robustness to phase noise...")
    noise_levels = np.linspace(0.1, 2.5, 20)
    acc_moire, acc_clock, mean_gammas = [], [], []
    
    final_gamma_dist = None 
    
    for noise in noise_levels:
        X_test, Y_test = generate_phase_data(400, D, N_CLASSES, noise)
        
        am, _ = evaluate_model(model_moire, X_test, Y_test)
        ac, g_vals = evaluate_model(model_clock, X_test, Y_test)
        
        acc_moire.append(am)
        acc_clock.append(ac)
        mean_gammas.append(np.mean(g_vals))
        final_gamma_dist = g_vals # Keep overwriting to get the last one (highest noise)

    # ── 6. Plotting ───────────────────────────────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f"Forced Clockfield: τ = 50.0", fontsize=16, fontweight='bold')

    # Plot 1: Generalization
    ax = axes[0]
    ax.plot(noise_levels, acc_moire, 'o-', color='steelblue', label='Standard Moiré')
    ax.plot(noise_levels, acc_clock, 's-', color='crimson', label='Clockfield (τ=50.0)')
    ax.axvline(TRAIN_NOISE, color='k', linestyle='--', alpha=0.5, label='Training Noise')
    ax.set_title('Robustness to Phase Frustration')
    ax.set_xlabel('Test Data Phase Noise (σ)')
    ax.set_ylabel('Classification Accuracy')
    ax.legend()
    ax.grid(alpha=0.3)

    # Plot 2: Mean Gamma
    ax = axes[1]
    ax.plot(noise_levels, mean_gammas, 's-', color='darkviolet')
    ax.set_title('Average Γ vs Noise')
    ax.set_xlabel('Test Data Phase Noise (σ)')
    ax.set_ylabel('Mean Γ Value')
    ax.set_ylim(-0.1, 1.1)
    ax.grid(alpha=0.3)
    
    # Plot 3: The Smoking Gun (Histogram of Γ at High Noise)
    ax = axes[2]
    ax.hist(final_gamma_dist, bins=50, color='indigo', alpha=0.7, edgecolor='black')
    ax.set_title('Distribution of Γ at High Noise (σ=2.5)\n(The Bimodal Phase Transition)')
    ax.set_xlabel('Proper Time Conformal Factor (Γ)')
    ax.set_ylabel('Frequency (Attention Channels)')
    ax.set_xlim(-0.05, 1.05)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig('exp3_forced_tau_results.png', dpi=150)
    print("\nSaved: exp3_forced_tau_results.png")

if __name__ == "__main__":
    run()