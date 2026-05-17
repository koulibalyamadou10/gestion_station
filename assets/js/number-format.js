/**
 * Formatage numérique fr-FR à la saisie : 15 000, 15 000,99, 15 000.99
 */
(function (global) {
    function parseAmountPlain(value) {
        if (value === null || value === undefined) return '';
        return String(value).replace(/\s/g, '').replace(/\u00a0/g, '').replace(',', '.').trim();
    }

    function parseAmountInput(value) {
        const plain = parseAmountPlain(value);
        if (plain === '' || plain === '-') return 0;
        const parsed = parseFloat(plain);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function formatAmount(value) {
        let n = Number(value);
        if (!Number.isFinite(n)) n = 0;
        const rounded = Math.round(n * 100) / 100;
        return rounded.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
    }

    function attachLiveNumberFormatting(inputEl, onUpdate) {
        if (!inputEl || inputEl.dataset.numberFormatAttached === '1') return;
        inputEl.dataset.numberFormatAttached = '1';

        function applyFormat() {
            const raw = inputEl.value;
            if (!raw.trim()) {
                onUpdate?.();
                return;
            }
            const atEnd = inputEl.selectionStart === raw.length;
            inputEl.value = formatAmount(parseAmountInput(raw));
            if (atEnd) {
                const len = inputEl.value.length;
                inputEl.setSelectionRange(len, len);
            }
            onUpdate?.();
        }

        inputEl.addEventListener('input', function () {
            inputEl.value = inputEl.value.replace(/[^\d\s,\.]/g, '');
            applyFormat();
        });
        inputEl.addEventListener('blur', function () {
            if (inputEl.value.trim()) {
                inputEl.value = formatAmount(parseAmountInput(inputEl.value));
            }
            onUpdate?.();
        });
    }

    function initNumberInputs(root) {
        (root || document).querySelectorAll('.js-number-input').forEach(function (el) {
            attachLiveNumberFormatting(el);
        });
    }

    function stripNumberInputsForSubmit(form) {
        if (!form) return;
        form.querySelectorAll('.js-number-input').forEach(function (el) {
            const plain = parseAmountPlain(el.value);
            if (plain !== '') el.value = plain;
        });
    }

    global.NumberFormat = {
        parseAmountPlain: parseAmountPlain,
        parseAmountInput: parseAmountInput,
        formatAmount: formatAmount,
        attachLiveNumberFormatting: attachLiveNumberFormatting,
        initNumberInputs: initNumberInputs,
        stripNumberInputsForSubmit: stripNumberInputsForSubmit,
    };

    document.addEventListener('DOMContentLoaded', function () {
        initNumberInputs();
        document.querySelectorAll('form').forEach(function (form) {
            form.addEventListener('submit', function () {
                stripNumberInputsForSubmit(form);
            });
        });
    });
})(window);
