/**
 * Formatage numérique fr-FR à la saisie.
 * - js-number-input : montants / quantités (0 à 2 décimales)
 * - js-decimal-input : quantités avec toujours 2 décimales au blur (ex. 25 000,58)
 * - js-integer-input : entiers avec séparateur de milliers (ex. numéro de pompe)
 */
(function (global) {
    const FORMATTED_INPUT_SELECTOR =
        '.js-number-input, .js-decimal-input, .js-integer-input';

    function parseAmountPlain(value) {
        if (value === null || value === undefined) return '';
        return String(value)
            .replace(/\s/g, '')
            .replace(/\u00a0/g, '')
            .replace(',', '.')
            .trim();
    }

    function parseAmountInput(value) {
        const plain = parseAmountPlain(value);
        if (plain === '' || plain === '-') return 0;
        const parsed = parseFloat(plain);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function round2(n) {
        return Math.round(n * 100) / 100;
    }

    function formatAmount(value) {
        let n = Number(value);
        if (!Number.isFinite(n)) n = 0;
        const rounded = round2(n);
        return rounded.toLocaleString('fr-FR', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
        });
    }

    /** Toujours 2 chiffres après la virgule : 15 000,00 — 25 000,58 */
    function formatDecimal(value) {
        let n = Number(value);
        if (!Number.isFinite(n)) n = 0;
        const rounded = round2(n);
        return rounded.toLocaleString('fr-FR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    /** Entier avec séparateur de milliers, sans décimales */
    function formatInteger(value) {
        let n = Math.round(Number(value));
        if (!Number.isFinite(n)) n = 0;
        if (n < 0) n = 0;
        return n.toLocaleString('fr-FR', { maximumFractionDigits: 0 });
    }

    function formatIntPartWithSpaces(intDigits) {
        if (!intDigits) return '';
        const n = parseInt(intDigits, 10);
        if (!Number.isFinite(n)) return intDigits;
        return n.toLocaleString('fr-FR', { maximumFractionDigits: 0 });
    }

    /**
     * Formatage léger pendant la saisie (ne force pas ,00 tant que l'utilisateur tape).
     */
    function formatPartialDecimal(raw) {
        let s = String(raw).replace(/\s/g, '').replace(/\u00a0/g, '').replace(/\./g, ',');
        s = s.replace(/[^\d,]/g, '');
        const commaIdx = s.indexOf(',');
        let intDigits = '';
        let fracDigits = '';
        let trailingComma = false;

        if (commaIdx >= 0) {
            intDigits = s.slice(0, commaIdx).replace(/,/g, '');
            fracDigits = s.slice(commaIdx + 1).replace(/,/g, '').slice(0, 2);
            trailingComma = s.endsWith(',');
        } else {
            intDigits = s;
        }

        if (!intDigits && !fracDigits && !trailingComma) return '';

        const formattedInt = intDigits ? formatIntPartWithSpaces(intDigits) : (trailingComma || fracDigits ? '0' : '');

        if (trailingComma && !fracDigits) {
            return formattedInt + ',';
        }
        if (fracDigits || trailingComma) {
            return formattedInt + ',' + fracDigits;
        }
        return formattedInt;
    }

    function formatPartialAmount(raw) {
        return formatPartialDecimal(raw);
    }

    function formatPartialInteger(raw) {
        const digits = String(raw).replace(/\D/g, '');
        if (!digits) return '';
        return formatIntPartWithSpaces(digits);
    }

    function getFormatMode(inputEl) {
        if (inputEl.classList.contains('js-decimal-input')) return 'decimal';
        if (inputEl.classList.contains('js-integer-input')) return 'integer';
        return 'amount';
    }

    function formatByMode(value, mode) {
        if (mode === 'decimal') return formatDecimal(value);
        if (mode === 'integer') return formatInteger(value);
        return formatAmount(value);
    }

    function formatPartialByMode(raw, mode) {
        if (mode === 'decimal') return formatPartialDecimal(raw);
        if (mode === 'integer') return formatPartialInteger(raw);
        return formatPartialAmount(raw);
    }

    function attachLiveNumberFormatting(inputEl, onUpdate, modeOverride) {
        if (!inputEl || inputEl.dataset.numberFormatAttached === '1') return;
        inputEl.dataset.numberFormatAttached = '1';

        const mode = modeOverride || getFormatMode(inputEl);

        function applyPartialFormat() {
            const raw = inputEl.value;
            const atEnd = inputEl.selectionStart === raw.length;
            if (!raw.trim()) {
                onUpdate?.();
                return;
            }
            inputEl.value = formatPartialByMode(raw, mode);
            if (atEnd) {
                const len = inputEl.value.length;
                inputEl.setSelectionRange(len, len);
            }
            onUpdate?.();
        }

        function applyFinalFormat() {
            if (!inputEl.value.trim()) {
                onUpdate?.();
                return;
            }
            inputEl.value = formatByMode(parseAmountInput(inputEl.value), mode);
            onUpdate?.();
        }

        inputEl.addEventListener('input', function () {
            applyPartialFormat();
        });
        inputEl.addEventListener('blur', function () {
            applyFinalFormat();
        });
    }

    function initInputs(root, selector, mode) {
        (root || document).querySelectorAll(selector).forEach(function (el) {
            attachLiveNumberFormatting(el, null, mode);
        });
    }

    function initNumberInputs(root) {
        initInputs(root, '.js-number-input', 'amount');
    }

    function initDecimalInputs(root) {
        initInputs(root, '.js-decimal-input', 'decimal');
    }

    function initIntegerInputs(root) {
        initInputs(root, '.js-integer-input', 'integer');
    }

    function initAllNumberInputs(root) {
        initInputs(root, '.js-number-input', 'amount');
        initInputs(root, '.js-decimal-input', 'decimal');
        initInputs(root, '.js-integer-input', 'integer');
    }

    function stripNumberInputsForSubmit(form) {
        if (!form) return;
        form.querySelectorAll(FORMATTED_INPUT_SELECTOR).forEach(function (el) {
            const plain = parseAmountPlain(el.value);
            if (plain !== '') el.value = plain;
        });
    }

    global.NumberFormat = {
        parseAmountPlain: parseAmountPlain,
        parseAmountInput: parseAmountInput,
        formatAmount: formatAmount,
        formatDecimal: formatDecimal,
        formatInteger: formatInteger,
        formatPartialDecimal: formatPartialDecimal,
        attachLiveNumberFormatting: attachLiveNumberFormatting,
        initNumberInputs: initNumberInputs,
        initDecimalInputs: initDecimalInputs,
        initIntegerInputs: initIntegerInputs,
        initAllNumberInputs: initAllNumberInputs,
        stripNumberInputsForSubmit: stripNumberInputsForSubmit,
    };

    document.addEventListener('DOMContentLoaded', function () {
        initAllNumberInputs();
        document.querySelectorAll('form').forEach(function (form) {
            form.addEventListener('submit', function () {
                stripNumberInputsForSubmit(form);
            });
        });
    });
})(window);
