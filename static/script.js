document.addEventListener("DOMContentLoaded", function () {
  function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  }

  // التحقق من نموذج تسجيل الدخول
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", function (event) {
      const email = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value.trim();

      if (!validateEmail(email)) {
        alert("يرجى إدخال بريد إلكتروني صالح.");
        event.preventDefault();
      } else if (password.length < 6) {
        alert("كلمة المرور يجب أن تكون 6 أحرف على الأقل.");
        event.preventDefault();
      }
    });
  }

  // التحقق من نموذج التسجيل
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", function (event) {
      const username = document.getElementById("username").value.trim();
      const email = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value.trim();
      const confirm_password = document
        .getElementById("confirm_password")
        .value.trim();

      if (username.length < 3) {
        alert("اسم المستخدم يجب أن يكون 3 أحرف على الأقل.");
        event.preventDefault();
      } else if (!validateEmail(email)) {
        alert("يرجى إدخال بريد إلكتروني صالح.");
        event.preventDefault();
      } else if (password.length < 6) {
        alert("كلمة المرور يجب أن تكون 6 أحرف على الأقل.");
        event.preventDefault();
      } else if (confirm_password !== password) {
        alert("كلمة المرور وتأكيد كلمة المرور يجب أن يتطابقا.");
        event.preventDefault();
      }
    });
  }
});
