function updateTotal(input) {
  let studyMode = input.dataset.studyMode;
  let group = input.dataset.group;

  let maleInput = document.querySelector(
    `input[data-study-mode="${studyMode}"][data-group="${group}"][data-type="male"]`
  );
  let femaleInput = document.querySelector(
    `input[data-study-mode="${studyMode}"][data-group="${group}"][data-type="female"]`
  );

  let totalField = document.querySelector(
    `.total[data-study-mode="${studyMode}"][data-group="${group}"]`
  );
  let grandTotalField = document.querySelector(
    `.grand-total[data-study-mode="${studyMode}"]`
  );

  let maleValue = parseFloat(maleInput.value) || 0;
  let femaleValue = parseFloat(femaleInput.value) || 0;

  let total = maleValue + femaleValue;
  totalField.textContent = total;

  let saudiTotal =
    parseFloat(
      document.querySelector(
        `.total[data-study-mode="${studyMode}"][data-group="سعودي"]`
      ).textContent
    ) || 0;
  let nonSaudiTotal =
    parseFloat(
      document.querySelector(
        `.total[data-study-mode="${studyMode}"][data-group="غير سعودي"]`
      ).textContent
    ) || 0;
  grandTotalField.textContent = saudiTotal + nonSaudiTotal;
}
