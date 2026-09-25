import Swal from 'sweetalert2';

export interface DestructivePreview {
  path?: string;
  item_count?: number | string;
  total_size?: string;
  human_size?: string;
  sample_paths?: string[];
  risk_tier?: 'low' | 'medium' | 'high';
}

export interface ConfirmationResult {
  confirmed: boolean;
  steps: string[];
  path?: string;
}

/**
 * Executes the multi-step SweetAlert2 confirmation sequence:
 * - Medium tier (clean_temp_and_cache, empty_trash): Modal 1 (Preview) + Modal 3 (Final 3s delay)
 * - High tier (delete_path): Modal 1 (Preview) + Modal 2 (Typed Path Match) + Modal 3 (Final 3s delay)
 */
export async function confirmDestructiveAction(
  preview: DestructivePreview,
  riskTier: 'low' | 'medium' | 'high' = 'medium',
  isWindows: boolean = true
): Promise<ConfirmationResult> {
  const stepsCompleted: string[] = [];
  const targetPath = preview.path || 'selected target';
  const itemCount = preview.item_count || 'multiple';
  const totalSize = preview.total_size || preview.human_size || 'variable size';

  // STEP 1: Preview Modal
  const previewResult = await Swal.fire({
    title: 'Destructive Action Preview',
    html: `
      <div style="text-align: left; font-size: 14px; line-height: 1.6;">
        <p style="margin-bottom: 12px; color: #dc2626; font-weight: 600;">
          ⚠️ This operation cannot be undone.
        </p>
        <p>This will permanently delete <strong>${itemCount}</strong> items (approx <strong>${totalSize}</strong>) inside:</p>
        <code style="display: block; background: #f1f5f9; padding: 8px; border-radius: 6px; word-break: break-all; margin: 8px 0; color: #0f172a; font-family: monospace;">
          ${targetPath}
        </code>
      </div>
    `,
    icon: 'warning',
    showCancelButton: true,
    confirmButtonText: 'Continue',
    cancelButtonText: 'Cancel',
    confirmButtonColor: '#2563eb',
    cancelButtonColor: '#64748b',
    reverseButtons: true,
    focusCancel: true,
  });

  if (!previewResult.isConfirmed) {
    return { confirmed: false, steps: stepsCompleted };
  }
  stepsCompleted.push('preview');

  // STEP 2: Typed-Confirmation Modal (High Risk only, e.g. delete_path)
  if (riskTier === 'high') {
    const typedResult = await Swal.fire({
      title: 'Confirm Folder Path',
      html: `
        <div style="text-align: left; font-size: 14px;">
          <p style="margin-bottom: 8px;">To prevent accidental data loss, please type the exact folder path below to confirm:</p>
          <code style="display: block; background: #f8fafc; padding: 6px; border: 1px solid #e2e8f0; border-radius: 4px; word-break: break-all; margin-bottom: 12px; font-family: monospace;">
            ${targetPath}
          </code>
        </div>
      `,
      input: 'text',
      inputPlaceholder: 'Type path here to confirm...',
      showCancelButton: true,
      confirmButtonText: 'Verify & Proceed',
      cancelButtonText: 'Cancel',
      confirmButtonColor: '#dc2626',
      cancelButtonColor: '#64748b',
      reverseButtons: true,
      inputValidator: (value) => {
        if (!value) {
          return 'You must type the target path to proceed.';
        }
        const matches = isWindows
          ? value.trim().toLowerCase() === targetPath.trim().toLowerCase()
          : value.trim() === targetPath.trim();

        if (!matches) {
          return 'The typed path does not match the target path.';
        }
        return null;
      },
    });

    if (!typedResult.isConfirmed) {
      return { confirmed: false, steps: stepsCompleted };
    }
    stepsCompleted.push('typed_path');
  }

  // STEP 3: Final Irreversible-Action Modal with 3-second disabled delay
  let secondsRemaining = 3;
  const finalResult = await Swal.fire({
    title: 'Irreversible Action',
    html: `
      <div style="font-size: 14px; color: #475569;">
        <p style="color: #b91c1c; font-weight: 700; margin-bottom: 10px;">
          Are you completely certain?
        </p>
        <p>This action is immediate and non-recoverable. Items will not be moved to trash.</p>
        <p style="margin-top: 12px; font-size: 12px; color: #64748b;">
          Confirm button activates in <span id="swal-countdown" style="font-weight: 700; color: #b91c1c;">3</span> seconds...
        </p>
      </div>
    `,
    icon: 'error',
    showCancelButton: true,
    confirmButtonText: 'Yes, permanently execute',
    cancelButtonText: 'Cancel',
    confirmButtonColor: '#dc2626',
    cancelButtonColor: '#64748b',
    reverseButtons: true,
    focusCancel: true,
    didOpen: () => {
      const confirmBtn = Swal.getConfirmButton();
      if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.style.opacity = '0.5';
        confirmBtn.style.cursor = 'not-allowed';
      }

      const timer = setInterval(() => {
        secondsRemaining -= 1;
        const countdownEl = document.getElementById('swal-countdown');
        if (countdownEl) {
          countdownEl.textContent = String(Math.max(0, secondsRemaining));
        }

        if (secondsRemaining <= 0) {
          clearInterval(timer);
          if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.style.opacity = '1.0';
            confirmBtn.style.cursor = 'pointer';
          }
        }
      }, 1000);
    },
  });

  if (!finalResult.isConfirmed) {
    return { confirmed: false, steps: stepsCompleted };
  }
  stepsCompleted.push('final');

  return {
    confirmed: true,
    steps: stepsCompleted,
    path: targetPath,
  };
}
