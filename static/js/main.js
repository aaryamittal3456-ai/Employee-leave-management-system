/* ═══════════════════════════════════════════════════════════
   LeaveFlow — Main JavaScript
   ═══════════════════════════════════════════════════════════ */

'use strict';

/* ── Role toggle (auth page) ──────────────────────────────── */
function updateRole() {
  const empRadio = document.querySelector('input[value="employee"]');
  const admRadio = document.querySelector('input[value="admin"]');
  const empBtn   = document.getElementById('empBtn');
  const admBtn   = document.getElementById('admBtn');

  if (!empRadio || !admRadio) return;

  if (empBtn) empBtn.classList.toggle('selected', empRadio.checked);
  if (admBtn) admBtn.classList.toggle('selected', admRadio.checked);
}

/* ── Leave day calculator (employee dashboard) ────────────── */
function calcDays() {
  const startInput = document.getElementById('startDate');
  const endInput   = document.getElementById('endDate');
  const display    = document.getElementById('daysDisplay');

  if (!startInput || !endInput || !display) return;

  const s = startInput.value;
  const e = endInput.value;

  if (s && e) {
    const diff = (new Date(e) - new Date(s)) / 86_400_000 + 1;
    if (diff > 0) {
      display.textContent = diff + (diff === 1 ? ' day' : ' days');
      display.style.color = '';
    } else {
      display.textContent = '⚠ End date must be after start date';
      display.style.color = '#dc2626';
    }
  } else {
    display.textContent = '— select dates below —';
    display.style.color = '';
  }
}

/* ── Set date input minimums to today ─────────────────────── */
function setDateMinimums() {
  const today = new Date().toISOString().split('T')[0];
  ['startDate', 'endDate'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.min = today;
  });
}

/* ── Auto-dismiss flash messages after 5 s ────────────────── */
function autoDismissFlash() {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity    = '0';
      setTimeout(() => el.remove(), 400);
    }, 5000);
  });
}

/* ── Confirm before deny action ───────────────────────────── */
function bindDenyConfirm() {
  document.querySelectorAll('.btn-deny').forEach(btn => {
    btn.addEventListener('click', function (e) {
      if (!confirm('Are you sure you want to deny this leave request?')) {
        e.preventDefault();
      }
    });
  });
}

/* ── Init on DOM ready ────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  updateRole();
  setDateMinimums();
  autoDismissFlash();
  bindDenyConfirm();

  /* Attach live listeners */
  const startDate = document.getElementById('startDate');
  const endDate   = document.getElementById('endDate');
  if (startDate) startDate.addEventListener('change', calcDays);
  if (endDate)   endDate.addEventListener('change', calcDays);

  document.querySelectorAll('input[name="role"]').forEach(radio => {
    radio.addEventListener('change', updateRole);
  });
});
