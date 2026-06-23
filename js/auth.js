document.addEventListener("DOMContentLoaded", () => {
  document.body.style.visibility = "visible";
  document.body.style.opacity = "1";

  const loginButton = document.getElementById("btnEntrar");
  const registerButton = document.getElementById("btnCadastrar");

  function showFeedback(element, message, color = "#e05555") {
    if (!element) return;
    element.textContent = message;
    element.style.color = color;
    element.style.display = "block";
  }

  async function readJson(response) {
    try {
      return await response.json();
    } catch (error) {
      return {};
    }
  }

  if (loginButton) {
    loginButton.addEventListener("click", async () => {
      const email = document.getElementById("inputEmail")?.value.trim() || "";
      const password = document.getElementById("inputSenha")?.value || "";
      const feedback = document.getElementById("loginFeedback");

      if (feedback) {
        feedback.style.display = "none";
        feedback.textContent = "";
      }

      if (!email || !password) {
        showFeedback(feedback, "Preencha e-mail e senha.");
        return;
      }

      loginButton.disabled = true;
      loginButton.textContent = "Entrando...";

      try {
        const response = await fetch("/api/users/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        const data = await readJson(response);

        if (response.ok && data.token) {
          localStorage.setItem("token", data.token);
          window.location.href = "/";
          return;
        }

        showFeedback(feedback, data.error || "Erro ao fazer login.");
      } catch (error) {
        showFeedback(feedback, "Nao foi possivel conectar ao servidor.");
      } finally {
        loginButton.disabled = false;
        loginButton.textContent = "Entrar";
      }
    });
  }

  if (registerButton) {
    registerButton.addEventListener("click", async () => {
      const email = document.getElementById("email")?.value.trim() || "";
      const password = document.getElementById("password")?.value || "";
      const confirm_password = document.getElementById("confirm_password")?.value || "";
      const feedback = document.getElementById("cadastroFeedback");

      if (feedback) {
        feedback.style.display = "none";
        feedback.textContent = "";
      }

      if (!email || !password || !confirm_password) {
        showFeedback(feedback, "Preencha todos os campos.");
        return;
      }

      registerButton.disabled = true;
      registerButton.textContent = "Cadastrando...";

      try {
        const response = await fetch("/api/users/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password, confirm_password }),
        });

        const data = await readJson(response);

        if (!response.ok) {
          showFeedback(feedback, data.error || "Erro ao realizar cadastro.");
          return;
        }

        const loginResponse = await fetch("/api/users/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        const loginData = await readJson(loginResponse);

        if (loginResponse.ok && loginData.token) {
          localStorage.setItem("token", loginData.token);
          window.location.href = "/";
          return;
        }

        showFeedback(feedback, data.message || "Conta criada. Faca login para continuar.", "#3a9c4e");
        setTimeout(() => { window.location.href = "/login"; }, 1500);
      } catch (error) {
        showFeedback(feedback, "Nao foi possivel conectar ao servidor.");
      } finally {
        registerButton.disabled = false;
        registerButton.textContent = "Criar Conta";
      }
    });
  }
});
