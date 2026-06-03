'use strict';

class CalculatorUI {
  constructor() {
    /** @type {string} Current expression buffer shown on the display. */
    this.expression = '';
    /** @type {HTMLElement} Reference to the display element. */
    this.display = document.getElementById('display');
  }

  /**
   * Binds click listeners on all .btn elements via event delegation on the
   * button grid container (#btn-grid).
   */
  init() {
    const grid = document.getElementById('btn-grid');
    if (!grid) {
      console.error('CalculatorUI: #btn-grid element not found.');
      return;
    }
    grid.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn');
      if (!btn) return;
      // Prefer an explicit data-value attribute; fall back to visible text.
      const value = btn.dataset.value !== undefined
        ? btn.dataset.value
        : btn.textContent.trim();
      this.handleButton(value);
    });
  }

  /**
   * Dispatches on value:
   *   - 'C'  → clears the expression
   *   - '='  → sends the expression to the backend
   *   - '⌫'  → removes the last character
   *   - anything else → appends to the expression buffer
   *
   * @param {string} value
   */
  handleButton(value) {
    switch (value) {
      case 'C':
        this.expression = '';
        this.updateDisplay('0');
        break;

      case '=':
        this.sendExpression();
        break;

      case '⌫':
        this.expression = this.expression.slice(0, -1);
        this.updateDisplay(this.expression || '0');
        break;

      default:
        this.expression += value;
        this.updateDisplay(this.expression);
    }
  }

  /**
   * POSTs { expression } to /calculate via fetch().
   * On success updates the display with the result (and stores it as the new
   * expression so the result can be used in further calculations).
   * On network or server error shows the error message briefly, then restores
   * the prior expression.
   */
  async sendExpression() {
    const prior = this.expression;

    try {
      const response = await fetch('/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expression: this.expression }),
      });

      const data = await response.json();

      if (!response.ok) {
        const msg = data.error || 'Error';
        this.updateDisplay(msg);
        setTimeout(() => {
          this.expression = prior;
          this.updateDisplay(prior || '0');
        }, 1500);
        return;
      }

      const result = String(data.result);
      this.expression = result;
      this.updateDisplay(result);
    } catch (_err) {
      this.updateDisplay('Error');
      setTimeout(() => {
        this.expression = prior;
        this.updateDisplay(prior || '0');
      }, 1500);
    }
  }

  /**
   * Sets display.textContent to text.
   * Trims a trailing ".0" for clean integer results (e.g. "5.0" → "5").
   *
   * @param {string} text
   */
  updateDisplay(text) {
    let display = String(text);
    // Only strip the redundant decimal for pure integer-valued results such as
    // "5.0" or "-3.0"; leave expression strings like "2.0+3" untouched.
    if (/^-?\d+\.0$/.test(display)) {
      display = display.slice(0, -2);
    }
    this.display.textContent = display;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const ui = new CalculatorUI();
  ui.init();
});
