const Api = (() => {
  const apiBase = "http://192.168.9.212:3000";

  function getToken() {
    return localStorage.getItem("access_token");
  }

  function setToken(token) {
    if (!token) localStorage.removeItem("access_token");
    else localStorage.setItem("access_token", token);
  }

  function decodeJwt(token) {
    try {
      const payload = token.split(".")[1];
      const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
      return JSON.parse(decodeURIComponent(escape(json)));
    } catch {
      return null;
    }
  }

  async function request(path, { method = "GET", body, auth = false, form = false } = {}) {
    const headers = {};
    if (form) headers["Content-Type"] = "application/x-www-form-urlencoded";
    else headers["Content-Type"] = "application/json";

    if (auth) {
      const token = getToken();
      if (token) headers["Authorization"] = "Bearer " + token;
    }

    const res = await fetch(apiBase + path, {
      method,
      headers,
      body: body
        ? (form ? body : JSON.stringify(body))
        : undefined,
    });

    if (!res.ok) {
      let text = await res.text();
      const isAuthError = res.status === 401 || (auth && /учетные данные|credentials|Unauthorized/i.test(text));
      if (isAuthError && auth) {
        setToken(null);
        window.location.replace("/app/login.html?session_expired=1");
        throw new Error("SESSION_EXPIRED");
      }
      try {
        const json = JSON.parse(text);
        text = JSON.stringify(json, null, 2);
      } catch {}
      throw new Error(text || res.statusText);
    }

    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return await res.json();
    return await res.text();
  }

  return { request, getToken, setToken, decodeJwt };
})();

function $(id) { return document.getElementById(id); }

const I18N = {
  ru: {
    "lang.ru": "RU",
    "lang.kz": "KZ",
    "nav.home": "Главная",
    "nav.dashboard": "Кабинет",
    "nav.test": "Пройти тест",
    "nav.history": "История",
    "nav.plan": "План на неделю",
    "nav.analytics": "Аналитика",
    "nav.login": "Войти",
    "nav.register": "Регистрация",
    "nav.switch_user": "Сменить пользователя",
    "nav.logout": "Выйти",
    "nav.back_dashboard": "← В кабинет",
    "common.refresh": "Обновить",
    "common.open": "Открыть",
    "common.profile": "Профиль",
    "common.email": "Email",
    "common.role": "Роль",
    "common.user_id": "ID пользователя",
    "common.no_data": "—",
    "common.loading_error": "Ошибка загрузки",
    "common.loading_subjects_error": "Не удалось загрузить предметы: {message}",
    "common.select_subject": "Выберите предмет",
    "common.no_tests_yet": "Пока нет завершённых тестов.",
    "common.no_history_yet": "История попыток пока пуста.",
    "common.no_weak_topics": "Нет выраженных слабых тем",
    "common.support": "Поддержка",
    "role.student": "Студент",
    "role.teacher": "Преподаватель",
    "role.admin": "Администратор",
    "level.low": "низкий",
    "level.medium": "средний",
    "level.high": "высокий",
    "priority.high": "высокий",
    "priority.medium": "средний",
    "priority.low": "низкий",
    "test_type.quick": "Быстрый",
    "test_type.full": "Полный",
    "plan_item.review": "Повторение",
    "plan_item.theory": "Теория",
    "plan_item.practice": "Практика",
    "plan_item.test": "Тест",
    "plan_item.reflection": "Разбор",
    "subject.Казахский язык": "Казахский язык",
    "subject.Английский язык": "Английский язык",
    "subject.Русский язык": "Русский язык",
    "subject.Высшая математика": "Высшая математика",
    "subject.История Казахстана": "История Казахстана",
    "subject.Политология": "Политология",
    "subject.Социология": "Социология",
    "subject.Анализ данных": "Анализ данных",
    "subject.Web-программирование": "Web-программирование",
    "subject.Языки и технологии программирования": "Языки и технологии программирования",
    "subject.Системы управления базами данных": "Системы управления базами данных",
  },
  kz: {
    "lang.ru": "RU",
    "lang.kz": "KZ",
    "nav.home": "Басты бет",
    "nav.dashboard": "Кабинет",
    "nav.test": "Тест тапсыру",
    "nav.history": "Тарих",
    "nav.plan": "Апталық жоспар",
    "nav.analytics": "Талдау",
    "nav.login": "Кіру",
    "nav.register": "Тіркелу",
    "nav.switch_user": "Пайдаланушыны ауыстыру",
    "nav.logout": "Шығу",
    "nav.back_dashboard": "← Кабинетке",
    "common.refresh": "Жаңарту",
    "common.open": "Ашу",
    "common.profile": "Профиль",
    "common.email": "Email",
    "common.role": "Рөл",
    "common.user_id": "Пайдаланушы ID",
    "common.no_data": "—",
    "common.loading_error": "Жүктеу қатесі",
    "common.loading_subjects_error": "Пәндерді жүктеу мүмкін болмады: {message}",
    "common.select_subject": "Пәнді таңдаңыз",
    "common.no_tests_yet": "Әзірге аяқталған тесттер жоқ.",
    "common.no_history_yet": "Тапсыру тарихы әзірге бос.",
    "common.no_weak_topics": "Айқын әлсіз тақырыптар жоқ",
    "common.support": "Қолдау",
    "role.student": "Студент",
    "role.teacher": "Оқытушы",
    "role.admin": "Әкімші",
    "level.low": "төмен",
    "level.medium": "орташа",
    "level.high": "жоғары",
    "priority.high": "жоғары",
    "priority.medium": "орташа",
    "priority.low": "төмен",
    "test_type.quick": "Жылдам",
    "test_type.full": "Толық",
    "plan_item.review": "Қайталау",
    "plan_item.theory": "Теория",
    "plan_item.practice": "Тәжірибе",
    "plan_item.test": "Тест",
    "plan_item.reflection": "Талдау",
    "subject.Казахский язык": "Қазақ тілі",
    "subject.Английский язык": "Ағылшын тілі",
    "subject.Русский язык": "Орыс тілі",
    "subject.Высшая математика": "Жоғары математика",
    "subject.История Казахстана": "Қазақстан тарихы",
    "subject.Политология": "Саясаттану",
    "subject.Социология": "Әлеуметтану",
    "subject.Анализ данных": "Деректерді талдау",
    "subject.Web-программирование": "Web-бағдарламалау",
    "subject.Языки и технологии программирования": "Бағдарламалау тілдері мен технологиялары",
    "subject.Системы управления базами данных": "Деректер қорын басқару жүйелері",
  },
};

function getLang() {
  const value = localStorage.getItem("site_lang");
  return value === "kz" ? "kz" : "ru";
}

function setLang(lang) {
  localStorage.setItem("site_lang", lang === "kz" ? "kz" : "ru");
}

function t(key, params = {}) {
  const lang = getLang();
  const dict = I18N[lang] || I18N.ru;
  const fallback = I18N.ru[key] || key;
  let text = dict[key] || fallback;
  Object.entries(params).forEach(([name, value]) => {
    text = text.replace(new RegExp(`\\{${name}\\}`, "g"), String(value ?? ""));
  });
  return text;
}

function translateSubjectName(name) {
  return t(`subject.${name}`) || name || t("common.no_data");
}

function translateRole(role) {
  if (!role) return t("common.no_data");
  return t(`role.${role}`) || role;
}

function translateLevel(level) {
  if (!level) return t("common.no_data");
  const levelMap = {
    "низкий": "low",
    "средний": "medium",
    "высокий": "high",
    low: "low",
    medium: "medium",
    high: "high",
  };
  return t(`level.${levelMap[level] || level}`) || level;
}

function translatePriority(priority) {
  if (!priority) return t("common.no_data");
  return t(`priority.${priority}`) || priority;
}

function translateTestType(testType) {
  return t(`test_type.${testType}`) || testType || t("common.no_data");
}

function translatePlanItemType(itemType) {
  return t(`plan_item.${itemType}`) || itemType || t("common.no_data");
}

function _toUtcDate(value) {
  // Python utcnow() возвращает строку без 'Z' — браузер трактует её как локальное время.
  // Добавляем 'Z' чтобы явно указать UTC и получить правильное местное время.
  const s = String(value);
  return new Date(s.endsWith("Z") || s.includes("+") ? s : s + "Z");
}

function formatDate(value) {
  if (!value) return t("common.no_data");
  return _toUtcDate(value).toLocaleDateString(getLang() === "kz" ? "kk-KZ" : "ru-RU");
}

function formatDateTime(value) {
  if (!value) return t("common.no_data");
  return _toUtcDate(value).toLocaleString(getLang() === "kz" ? "kk-KZ" : "ru-RU");
}

function applyI18n(root = document) {
  if (!root || !root.querySelectorAll) return;
  document.documentElement.lang = getLang() === "kz" ? "kk" : "ru";
  root.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  root.querySelectorAll("[data-i18n-html]").forEach((node) => {
    node.innerHTML = t(node.dataset.i18nHtml);
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  root.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.textContent = t(node.dataset.i18nTitle);
    if (node.tagName === "TITLE") {
      document.title = node.textContent;
    }
  });
}

function injectLanguageToggle() {
  const containers = document.querySelectorAll(".site-header-main-left, .nav-actions");
  containers.forEach((container) => {
    if (!container || container.querySelector(".lang-switcher")) return;
    const wrap = document.createElement("div");
    wrap.className = "lang-switcher";

    const ruBtn = document.createElement("button");
    ruBtn.type = "button";
    ruBtn.className = `btn btn-lang${getLang() === "ru" ? " active" : ""}`;
    ruBtn.textContent = t("lang.ru");
    ruBtn.addEventListener("click", () => {
      if (getLang() === "ru") return;
      setLang("ru");
      window.location.reload();
    });

    const kzBtn = document.createElement("button");
    kzBtn.type = "button";
    kzBtn.className = `btn btn-lang${getLang() === "kz" ? " active" : ""}`;
    kzBtn.textContent = t("lang.kz");
    kzBtn.addEventListener("click", () => {
      if (getLang() === "kz") return;
      setLang("kz");
      window.location.reload();
    });

    wrap.appendChild(ruBtn);
    wrap.appendChild(kzBtn);
    container.appendChild(wrap);
  });
}

function initSiteI18n() {
  applyI18n(document);
  injectLanguageToggle();
}

function setText(id, text) {
  const el = $(id);
  if (el) el.textContent = text;
}

function renderJson(id, value, isError = false) {
  const el = $(id);
  if (!el) return;
  el.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  el.classList.toggle("error", !!isError);
}

function requireAuthOrRedirect() {
  const token = Api.getToken();
  if (!token) {
    window.location.href = "/app/login.html";
    return null;
  }
  const payload = Api.decodeJwt(token);
  if (!payload || !payload.sub || !payload.role) {
    Api.setToken(null);
    window.location.href = "/app/login.html";
    return null;
  }
  if (payload.exp && payload.exp * 1000 < Date.now()) {
    Api.setToken(null);
    window.location.href = "/app/login.html";
    return null;
  }
  return payload;
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initSiteI18n);
} else {
  initSiteI18n();
}

