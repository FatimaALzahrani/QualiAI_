function handleFileUpload() {
  const fileInput = document.getElementById("analysis-files");
  if (!fileInput) return;

  const fileList = document.getElementById("file-list");
  if (!fileList) return;

  fileList.innerHTML = "";

  for (const file of fileInput.files) {
    const li = document.createElement("li");
    li.className = "list-group-item";
    li.textContent = file.name;
    fileList.appendChild(li);
  }
}

const DEFAULT_STUDENT_STANDARDS = {
  3.1: {
    text: "يطبق البرنامج معايير وشروط معتمدة ومعلنة لقبول الطلاب وتسجيلهم وتوزيعهم، والانتقال إلى البرنامج ومعادلة ما تعلمه الطلاب سابقاً، بما يتناسب مع طبيعة البرنامج ومستواه.",
    mandatory: false,
  },
  3.2: {
    text: "يوفر البرنامج المعلومات الأساسية للطلاب، مثل: متطلبات الدراسة، الخدمات، والتكاليف المالية (إن وجدت)، بوسائل متنوعة.",
    mandatory: false,
  },
  3.3: {
    text: "يتوفر لطلاب البرنامج خدمات فعالة للإرشاد والتوجيه الأكاديمي والمهني والنفسي والاجتماعي، من خلال كوادر مؤهلة وكافية.",
    mandatory: true,
  },
  3.4: {
    text: "تطبق آليات ملائمة للتعرف على الطلاب الموهوبين والمبدعين والمتفوقين والمتعثرين في البرنامج، وتتوفر برامج مناسبة لرعاية وتحفيز ودعم كل فئة منهم.",
    mandatory: false,
  },
  3.5: {
    text: "يطبق البرنامج آلية فعالة للتواصل مع الخريجين وإشراكهم في مناسباته وأنشطته، واستطلاع آرائهم والاستفادة من خبراتهم، ودعمهم، وتوفر قواعد بيانات محدثة وشاملة عنهم.",
    mandatory: false,
  },
  3.6: {
    text: "تطبق آليات فعــالة لتقويم كفاية وجودة الخدمات المقدمة للطلاب وقياس رضاهم عنها، والاستفادة من النتائج في التحسين.",
    mandatory: true,
  },
};

let standardCount = 0;

const evidenceCountMap = {};

function initCriteriaPage() {
  const container = document.getElementById("student-standards-container");
  if (!container) return;

  container.innerHTML = "";
  standardCount = 0;

  for (const [id, standard] of Object.entries(DEFAULT_STUDENT_STANDARDS)) {
    addStandard(id, standard.text, standard.mandatory);
  }
}

/**
 * @param {string} id معرف المحك
 * @param {string} text نص المحك
 * @param {boolean} mandatory هل المحك إجباري
 */
function addStandard(id = "", text = "", mandatory = false) {
  const container = document.getElementById("student-standards-container");
  if (!container) return;

  if (!id) {
    id = `3.${standardCount + 1}`;
  }

  const standardDiv = document.createElement("div");
  standardDiv.className =
    "standard-box card p-3 mb-3 border border-primary shadow-sm";
  standardDiv.dataset.standardIndex = standardCount;

  standardDiv.innerHTML = `
          <div class="d-flex justify-content-between align-items-center">
              <div class="form-group flex-grow-1">
                  <label><strong>نص المحك (${id}):</strong></label>
                  <input type="text" class="form-control" name="standard_text[]" value="${text}" placeholder="اكتب نص المحك هنا" required />
                  <input type="hidden" name="standard_id[]" value="${id}" />
                  <input type="hidden" name="standard_mandatory[]" value="${mandatory}" />
              </div>
              <button type="button" class="btn btn-danger btn-sm mt-4 ms-2 delete-standard-btn" onclick="removeStandard(this)" ${
                mandatory ? 'disabled title="محك إجباري لا يمكن حذفه"' : ""
              }>
                  🗑 حذف المحك
              </button>
          </div>
          <div class="evidences-container mt-3">
              <!-- الشواهد تُضاف هنا -->
          </div>
          <button type="button" class="btn btn-secondary btn-sm mt-2" onclick="addEvidence(${standardCount})">
               إضافة شاهد
          </button>
      `;

  container.appendChild(standardDiv);

  evidenceCountMap[standardCount] = 0;

  standardCount++;
}

/**
 * @param {HTMLElement} button زر الحذف
 */
function removeStandard(button) {
  if (button.disabled) return;

  const standardBox = button.closest(".standard-box");
  if (standardBox) {
    standardBox.remove();
  }
}

/**
 * @param {number} standardIndex مؤشر المحك
 */
function addEvidence(standardIndex) {
  const standardBox = document.querySelector(
    `.standard-box[data-standard-index="${standardIndex}"]`
  );
  if (!standardBox) return;

  const evidencesContainer = standardBox.querySelector(".evidences-container");
  if (!evidencesContainer) return;

  const evidenceIndex = evidenceCountMap[standardIndex] || 0;

  const evidenceDiv = document.createElement("div");
  evidenceDiv.className = "evidence-item border rounded p-3 mt-3 bg-light";
  evidenceDiv.dataset.evidenceIndex = evidenceIndex;

  evidenceDiv.innerHTML = `
          <input type="hidden" name="evidence_index_${standardIndex}[]" value="${evidenceIndex}" />
          <div class="mb-2">
              <label>وصف الشاهد:</label>
              <input type="text" class="form-control" name="evidence_desc_${standardIndex}_${evidenceIndex}" placeholder="مثال: تقرير رضا الطلاب" required />
          </div>
          <div class="mb-2">
              <label>نوع الشاهد:</label>
              <select class="form-control" name="evidence_type_${standardIndex}_${evidenceIndex}" onchange="toggleEvidenceInput(this, ${standardIndex}, ${evidenceIndex})">
                  <option value="file">ملف</option>
                  <option value="link">رابط</option>
              </select>
          </div>
          <div class="evidence-file-input mb-2">
              <label>الملف:</label>
              <input type="file" class="form-control" name="evidence_file_${standardIndex}_${evidenceIndex}" />
          </div>
          <div class="evidence-link-input mb-2" style="display: none">
              <label>الرابط:</label>
              <input type="url" class="form-control" name="evidence_link_${standardIndex}_${evidenceIndex}" placeholder="https://..." />
          </div>
          <button type="button" class="btn btn-outline-danger btn-sm" onclick="removeEvidence(this) ">
              🗑 حذف الشاهد
          </button>
      `;

  evidencesContainer.appendChild(evidenceDiv);

  evidenceCountMap[standardIndex] = evidenceIndex + 1;
}

/**
 * @param {HTMLElement} button زر الحذف
 */
function removeEvidence(button) {
  const evidenceItem = button.closest(".evidence-item");
  if (evidenceItem) {
    evidenceItem.remove();
  }
}

/**
 * @param {HTMLElement} select عنصر الاختيار
 * @param {number} standardIndex مؤشر المحك
 * @param {number} evidenceIndex مؤشر الشاهد
 */
function toggleEvidenceInput(select, standardIndex, evidenceIndex) {
  const evidenceItem = select.closest(".evidence-item");
  if (!evidenceItem) return;

  const fileInput = evidenceItem.querySelector(".evidence-file-input");
  const linkInput = evidenceItem.querySelector(".evidence-link-input");

  if (select.value === "file") {
    fileInput.style.display = "block";
    linkInput.style.display = "none";
  } else {
    fileInput.style.display = "none";
    linkInput.style.display = "block";
  }
}

/**
 * @returns {boolean} هل النموذج صحيح
 */
function validateCriteriaForm() {
  const form = document.getElementById("criteria-form");
  if (!form) return false;

  const standardTexts = form.querySelectorAll('input[name="standard_text[]"]');
  if (standardTexts.length === 0) {
    alert("يجب إضافة محك واحد على الأقل");
    return false;
  }

  for (const input of standardTexts) {
    if (!input.value.trim()) {
      alert("يجب تعبئة نص جميع المحكات");
      input.focus();
      return false;
    }
  }

  const evidenceItems = form.querySelectorAll(".evidence-item");
  for (const item of evidenceItems) {
    const descInput = item.querySelector('input[name^="evidence_desc_"]');
    if (!descInput.value.trim()) {
      alert("يجب تعبئة وصف جميع الشواهد");
      descInput.focus();
      return false;
    }

    const typeSelect = item.querySelector('select[name^="evidence_type_"]');
    if (typeSelect.value === "file") {
      const fileInput = item.querySelector('input[type="file"]');
    } else {
      const linkInput = item.querySelector('input[type="url"]');
      if (!linkInput.value.trim()) {
        alert("يجب إدخال رابط للشاهد");
        linkInput.focus();
        return false;
      }
    }
  }

  return true;
}

document.addEventListener("DOMContentLoaded", function () {
  initCriteriaPage();

  const fileInput = document.getElementById("analysis-files");
  if (fileInput) {
    fileInput.addEventListener("change", handleFileUpload);
  }

  const form = document.getElementById("criteria-form");
  if (form) {
    form.addEventListener("submit", function (event) {
      if (!validateCriteriaForm()) {
        event.preventDefault();
      }
    });
  }
});
