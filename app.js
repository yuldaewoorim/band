const state = {
  session: null,
  adminData: null,
  memberData: null,
};

const elements = {
  authView: document.querySelector("#authView"),
  appView: document.querySelector("#appView"),
  adminView: document.querySelector("#adminView"),
  memberView: document.querySelector("#memberView"),
  loginForm: document.querySelector("#loginForm"),
  loginUsername: document.querySelector("#loginUsername"),
  loginPassword: document.querySelector("#loginPassword"),
  loginError: document.querySelector("#loginError"),
  logoutButton: document.querySelector("#logoutButton"),
  workspaceTitle: document.querySelector("#workspaceTitle"),
  sessionName: document.querySelector("#sessionName"),
  sessionRole: document.querySelector("#sessionRole"),
  sessionForm: document.querySelector("#sessionForm"),
  sessionTitle: document.querySelector("#sessionTitle"),
  sessionDate: document.querySelector("#sessionDate"),
  sessionList: document.querySelector("#sessionList"),
  refreshAdminButton: document.querySelector("#refreshAdminButton"),
  memberForm: document.querySelector("#memberForm"),
  memberName: document.querySelector("#memberName"),
  memberCode: document.querySelector("#memberCode"),
  memberUsername: document.querySelector("#memberUsername"),
  memberPassword: document.querySelector("#memberPassword"),
  memberList: document.querySelector("#memberList"),
  exportButton: document.querySelector("#exportButton"),
  adminCreateForm: document.querySelector("#adminCreateForm"),
  adminCreateName: document.querySelector("#adminCreateName"),
  adminCreateUsername: document.querySelector("#adminCreateUsername"),
  adminCreatePassword: document.querySelector("#adminCreatePassword"),
  adminPasswordForm: document.querySelector("#adminPasswordForm"),
  adminCurrentPassword: document.querySelector("#adminCurrentPassword"),
  adminNewPassword: document.querySelector("#adminNewPassword"),
  adminList: document.querySelector("#adminList"),
  reportForm: document.querySelector("#reportForm"),
  reportFrom: document.querySelector("#reportFrom"),
  reportTo: document.querySelector("#reportTo"),
  memberActiveSession: document.querySelector("#memberActiveSession"),
  memberHistory: document.querySelector("#memberHistory"),
};

elements.sessionDate.value = new Date().toISOString().slice(0, 10);

elements.loginForm.addEventListener("submit", onLogin);
elements.logoutButton.addEventListener("click", onLogout);
elements.sessionForm.addEventListener("submit", onCreateSession);
elements.memberForm.addEventListener("submit", onCreateMember);
elements.refreshAdminButton.addEventListener("click", loadAdminDashboard);
elements.exportButton.addEventListener("click", exportCsv);
elements.adminCreateForm?.addEventListener("submit", onCreateAdmin);
elements.adminPasswordForm?.addEventListener("submit", onAdminPasswordChange);
elements.reportForm?.addEventListener("submit", exportMemberSlides);

if (elements.reportFrom && elements.reportTo) {
  const today = new Date().toISOString().slice(0, 10);
  elements.reportFrom.value = today;
  elements.reportTo.value = today;
}

boot();

async function boot() {
  const session = await api("/api/session");
  state.session = session.user || null;
  renderShell();
  if (state.session?.role === "admin") await loadAdminDashboard();
  if (state.session?.role === "member") await loadMemberDashboard();
}

async function onLogin(event) {
  event.preventDefault();
  setError("");
  try {
    const response = await api("/api/login", {
      method: "POST",
      body: {
        username: elements.loginUsername.value.trim(),
        password: elements.loginPassword.value,
      },
    });
    state.session = response.user;
    elements.loginForm.reset();
    renderShell();
    if (state.session.role === "admin") await loadAdminDashboard();
    if (state.session.role === "member") await loadMemberDashboard();
  } catch (error) {
    setError(error.message);
  }
}

async function onLogout() {
  await api("/api/logout", { method: "POST" });
  state.session = null;
  state.adminData = null;
  state.memberData = null;
  renderShell();
}

async function onCreateSession(event) {
  event.preventDefault();
  await api("/api/admin/sessions", {
    method: "POST",
    body: {
      title: elements.sessionTitle.value.trim(),
      date: elements.sessionDate.value,
    },
  });
  elements.sessionForm.reset();
  elements.sessionDate.value = new Date().toISOString().slice(0, 10);
  await loadAdminDashboard();
}

async function onUpdateSession(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  await api(`/api/admin/sessions/${form.dataset.sessionEdit}/update`, {
    method: "POST",
    body: {
      title: String(formData.get("title") || "").trim(),
      date: String(formData.get("date") || "").trim(),
    },
  });
  await loadAdminDashboard();
}

async function onDeleteSession(sessionId) {
  if (!confirm("이 세션을 삭제하면 제출 기록도 함께 삭제됩니다. 계속할까요?")) return;
  await api(`/api/admin/sessions/${sessionId}/delete`, { method: "POST" });
  await loadAdminDashboard();
}

async function onCreateMember(event) {
  event.preventDefault();
  await api("/api/admin/members", {
    method: "POST",
    body: {
      name: elements.memberName.value.trim(),
      student_code: elements.memberCode.value.trim(),
      username: elements.memberUsername.value.trim(),
      password: elements.memberPassword.value,
    },
  });
  elements.memberForm.reset();
  await loadAdminDashboard();
}

async function onAdminPasswordChange(event) {
  event.preventDefault();
  await api("/api/admin/change-password", {
    method: "POST",
    body: {
      current_password: elements.adminCurrentPassword.value,
      new_password: elements.adminNewPassword.value,
    },
  });
  elements.adminPasswordForm.reset();
  alert("관리자 비밀번호가 변경되었습니다.");
}

async function onCreateAdmin(event) {
  event.preventDefault();
  await api("/api/admin/admins", {
    method: "POST",
    body: {
      name: elements.adminCreateName.value.trim(),
      username: elements.adminCreateUsername.value.trim(),
      password: elements.adminCreatePassword.value,
    },
  });
  elements.adminCreateForm.reset();
  await loadAdminDashboard();
}

async function onDeleteAdmin(adminId) {
  if (!confirm("이 관리자 계정을 삭제할까요?")) return;
  await api(`/api/admin/admins/${adminId}/delete`, { method: "POST" });
  await loadAdminDashboard();
}

async function onUpdateMember(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const formData = new FormData(form);
  await api(`/api/admin/members/${form.dataset.memberEdit}/update`, {
    method: "POST",
    body: {
      name: String(formData.get("name") || "").trim(),
      student_code: String(formData.get("student_code") || "").trim(),
      username: String(formData.get("username") || "").trim(),
    },
  });
  await loadAdminDashboard();
}

async function onDeleteMember(memberId) {
  if (!confirm("이 회원을 삭제하면 출결 기록도 함께 삭제됩니다. 계속할까요?")) return;
  await api(`/api/admin/members/${memberId}/delete`, { method: "POST" });
  await loadAdminDashboard();
}

async function loadAdminDashboard() {
  state.adminData = await api("/api/admin/dashboard");
  renderAdmin();
}

async function loadMemberDashboard() {
  state.memberData = await api("/api/member/dashboard");
  renderMember();
}

function renderShell() {
  const loggedIn = Boolean(state.session);
  elements.authView.hidden = loggedIn;
  elements.appView.hidden = !loggedIn;
  if (!loggedIn) {
    elements.adminView.hidden = true;
    elements.memberView.hidden = true;
    return;
  }
  elements.sessionName.textContent = state.session.name;
  elements.sessionRole.textContent = state.session.role === "admin" ? "관리자" : "회원";
  elements.workspaceTitle.textContent = state.session.role === "admin" ? "관리자 출결 대시보드" : "회원 출결 페이지";
  elements.adminView.hidden = state.session.role !== "admin";
  elements.memberView.hidden = state.session.role !== "member";
}

function renderAdmin() {
  const data = state.adminData;
  if (!data) return;

  elements.sessionList.innerHTML = "";
  if (data.sessions.length === 0) elements.sessionList.append(emptyCard("아직 생성된 출결 세션이 없습니다."));

  data.sessions.forEach((session) => {
    const card = document.createElement("article");
    card.className = "item-card";
    card.innerHTML = `
      <div class="item-head">
        <div>
          <h4>${escapeHtml(session.title)}</h4>
          <p class="meta">${escapeHtml(session.date)} · 제출 ${session.record_count}건</p>
          <p class="meta">지각 ${session.late_count || 0}명 · 결석 ${session.absent_count || 0}명</p>
        </div>
        <span class="pill ${session.is_open ? "open" : "closed"}">${session.is_open ? "진행중" : "마감"}</span>
      </div>
      <div class="split-actions">
        <button class="tiny-button" data-session-toggle="${session.id}">${session.is_open ? "마감하기" : "다시 열기"}</button>
        <button class="tiny-button" data-session-export="${session.id}">CSV 저장</button>
        <button class="tiny-button" data-session-delete="${session.id}">삭제</button>
      </div>
      <form class="stack-form compact-form" data-session-edit="${session.id}">
        <label>세션 이름<input name="title" type="text" value="${escapeAttribute(session.title)}" required /></label>
        <label>날짜<input name="date" type="date" value="${escapeAttribute(session.date)}" required /></label>
        <button class="tiny-button" type="submit">수정 저장</button>
      </form>
      <div class="list-grid">${session.records.map(renderAdminRecord).join("")}</div>
    `;
    elements.sessionList.append(card);
  });

  elements.sessionList.querySelectorAll("[data-session-toggle]").forEach((button) => {
    button.addEventListener("click", async () => {
      await api(`/api/admin/sessions/${button.dataset.sessionToggle}/toggle`, { method: "POST" });
      await loadAdminDashboard();
    });
  });
  elements.sessionList.querySelectorAll("[data-session-export]").forEach((button) => {
    button.addEventListener("click", () => {
      window.location.href = `/api/admin/sessions/${button.dataset.sessionExport}/export`;
    });
  });
  elements.sessionList.querySelectorAll("[data-session-delete]").forEach((button) => {
    button.addEventListener("click", () => onDeleteSession(button.dataset.sessionDelete));
  });
  elements.sessionList.querySelectorAll("[data-session-edit]").forEach((form) => {
    form.addEventListener("submit", onUpdateSession);
  });

  elements.memberList.innerHTML = "";
  if (data.members.length === 0) {
    elements.memberList.append(emptyCard("회원 계정이 아직 없습니다."));
  }

  data.members.forEach((member) => {
    const card = document.createElement("article");
    card.className = "item-card";
    card.innerHTML = `
      <div class="item-head">
        <div>
          <h4>${escapeHtml(member.name)}</h4>
          <p class="meta">${escapeHtml(member.student_code)} · ID ${escapeHtml(member.username)}</p>
        </div>
      </div>
      <form class="stack-form compact-form" data-member-edit="${member.id}">
        <label>이름<input name="name" type="text" value="${escapeAttribute(member.name)}" required /></label>
        <label>학번/기수<input name="student_code" type="text" value="${escapeAttribute(member.student_code)}" required /></label>
        <label>아이디<input name="username" type="text" value="${escapeAttribute(member.username)}" required /></label>
        <div class="split-actions">
          <button class="tiny-button" type="submit">회원 정보 수정</button>
          <button class="tiny-button" type="button" data-member-delete="${member.id}">회원 삭제</button>
        </div>
      </form>
      <form class="stack-form" data-password-form="${member.id}">
        <label>
          새 비밀번호
          <input name="password" type="text" placeholder="새 비밀번호 입력" required />
        </label>
        <button class="tiny-button" type="submit">비밀번호 변경</button>
      </form>
    `;
    elements.memberList.append(card);
  });

  elements.memberList.querySelectorAll("[data-password-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const password = new FormData(form).get("password");
      await api(`/api/admin/members/${form.dataset.passwordForm}/password`, {
        method: "POST",
        body: { password },
      });
      await loadAdminDashboard();
    });
  });

  elements.memberList.querySelectorAll("[data-member-edit]").forEach((form) => {
    form.addEventListener("submit", onUpdateMember);
  });

  elements.memberList.querySelectorAll("[data-member-delete]").forEach((button) => {
    button.addEventListener("click", () => onDeleteMember(button.dataset.memberDelete));
  });

  elements.adminList.innerHTML = "";
  if (!data.admins || data.admins.length === 0) {
    elements.adminList.append(emptyCard("관리자 계정이 없습니다."));
  } else {
    data.admins.forEach((admin) => {
      const card = document.createElement("article");
      card.className = "item-card";
      const isMe = state.session && Number(state.session.id) === Number(admin.id);
      card.innerHTML = `
        <div class="item-head">
          <div>
            <h4>${escapeHtml(admin.name)}</h4>
            <p class="meta">ID ${escapeHtml(admin.username)}${isMe ? " · 현재 로그인" : ""}</p>
          </div>
          <button class="tiny-button" type="button" data-admin-delete="${admin.id}" ${isMe ? "disabled" : ""}>관리자 삭제</button>
        </div>
      `;
      elements.adminList.append(card);
    });
    elements.adminList.querySelectorAll("[data-admin-delete]").forEach((button) => {
      if (!button.disabled) {
        button.addEventListener("click", () => onDeleteAdmin(button.dataset.adminDelete));
      }
    });
  }
}

function renderAdminRecord(record) {
  return `<div class="item-card"><div class="item-head"><div><strong>${escapeHtml(record.name)}</strong><p class="meta">${escapeHtml(record.student_code)} · ${statusLabel(record.status)}</p></div></div><p class="helper-text">${escapeHtml(record.memo || "메모 없음")}</p></div>`;
}

function renderMember() {
  const data = state.memberData;
  if (!data) return;
  elements.memberActiveSession.innerHTML = "";
  if (!data.open_sessions || data.open_sessions.length === 0) {
    elements.memberActiveSession.append(emptyCard("제출할 출결 세션이 없습니다."));
  } else {
    data.open_sessions.forEach((session) => {
      const wrapper = document.createElement("article");
      wrapper.className = "item-card";
      wrapper.innerHTML = `
        <div class="item-head">
          <div>
            <h4>${escapeHtml(session.title)}</h4>
            <p class="meta">${escapeHtml(session.date)}</p>
          </div>
          <span class="pill open">작성 가능</span>
        </div>
        <div class="status-buttons"></div>
        <label>
          메모
          <textarea class="member-memo" placeholder="지각 사유 등 필요한 내용을 남기세요"></textarea>
        </label>
        <button class="primary-button submit-attendance" type="button">내 출결 저장</button>
      `;
      elements.memberActiveSession.append(wrapper);

      const statusMount = wrapper.querySelector(".status-buttons");
      const statusNode = document.querySelector("#statusTemplate").content.cloneNode(true);
      statusMount.append(statusNode);

      wrapper.dataset.selectedStatus = "present";
      wrapper.querySelectorAll("[data-status]").forEach((button) => {
        if (button.dataset.status === "present") {
          button.classList.add("active-present");
        }
        button.addEventListener("click", () => {
          wrapper.querySelectorAll("[data-status]").forEach((item) => {
            item.className = "";
          });
          button.classList.add(`active-${button.dataset.status}`);
          wrapper.dataset.selectedStatus = button.dataset.status;
        });
      });

      wrapper.querySelector(".submit-attendance").addEventListener("click", async () => {
        await api("/api/member/attendance", {
          method: "POST",
          body: {
            session_id: session.id,
            status: wrapper.dataset.selectedStatus,
            memo: wrapper.querySelector(".member-memo").value.trim(),
          },
        });
        await loadMemberDashboard();
      });
    });
  }

  elements.memberHistory.innerHTML = "";
  if (!data.history || data.history.length === 0) {
    elements.memberHistory.append(emptyCard("아직 기록이 없습니다."));
    return;
  }
  data.history.forEach((record) => {
    const card = document.createElement("article");
    card.className = "item-card";
    const isOpen = Boolean(record.is_open);
    card.innerHTML = `
      <div class="item-head">
        <div>
          <h4>${escapeHtml(record.title)}</h4>
          <p class="meta">${escapeHtml(record.date)} · ${statusLabel(record.status)}</p>
        </div>
      </div>
      <p class="helper-text">${escapeHtml(record.memo || "메모 없음")}</p>
      ${
        isOpen
          ? `
      <div class="status-row history-status" data-history-status="${record.session_id}">
        <button data-status="present" type="button">출석</button>
        <button data-status="late" type="button">지각</button>
        <button data-status="absent" type="button">결석</button>
      </div>
      <label>
        메모 수정
        <textarea class="history-memo" data-history-memo="${record.session_id}" placeholder="메모를 수정하세요">${escapeHtml(record.memo || "")}</textarea>
      </label>
      <button class="tiny-button history-save" type="button" data-history-save="${record.session_id}">기록 수정 저장</button>
      <button class="tiny-button history-delete" type="button" data-history-delete="${record.session_id}">기록 삭제</button>
      `
          : `<p class="helper-text">마감된 세션은 수정할 수 없습니다.</p>`
      }
    `;
    elements.memberHistory.append(card);

    if (isOpen) {
      const statusWrap = card.querySelector(`[data-history-status="${record.session_id}"]`);
      statusWrap.querySelectorAll("[data-status]").forEach((button) => {
        if (button.dataset.status === record.status) {
          button.classList.add(`active-${record.status}`);
        }
        button.addEventListener("click", () => {
          statusWrap.querySelectorAll("[data-status]").forEach((item) => {
            item.className = "";
          });
          button.classList.add(`active-${button.dataset.status}`);
          statusWrap.dataset.selectedStatus = button.dataset.status;
        });
      });
      statusWrap.dataset.selectedStatus = record.status;

      const saveButton = card.querySelector(`[data-history-save="${record.session_id}"]`);
      const deleteButton = card.querySelector(`[data-history-delete="${record.session_id}"]`);
      const memoInput = card.querySelector(`[data-history-memo="${record.session_id}"]`);
      saveButton.addEventListener("click", async () => {
        await api("/api/member/attendance", {
          method: "POST",
          body: {
            session_id: record.session_id,
            status: statusWrap.dataset.selectedStatus,
            memo: memoInput.value.trim(),
          },
        });
        await loadMemberDashboard();
      });
      deleteButton.addEventListener("click", async () => {
        if (!confirm("이 출결 기록을 삭제하고 제출 전 상태로 되돌릴까요?")) return;
        await api("/api/member/attendance/delete", {
          method: "POST",
          body: { session_id: record.session_id },
        });
        await loadMemberDashboard();
      });
    }
  });
}

function emptyCard(text) {
  const card = document.createElement("div");
  card.className = "empty-card";
  card.textContent = text;
  return card;
}

async function exportCsv() {
  const firstSession = state.adminData?.sessions?.[0];
  if (!firstSession) return;
  window.location.href = `/api/admin/sessions/${firstSession.id}/export`;
}

async function exportMemberSlides(event) {
  event.preventDefault();
  const from = elements.reportFrom.value;
  const to = elements.reportTo.value;
  if (!from || !to) return;
  window.location.href = `/api/admin/reports/member-slides?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`;
}

async function api(url, options = {}) {
  const response = await fetch(url, {
    method: options.method || "GET",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: "요청 실패" }));
    throw new Error(error.error || "요청 실패");
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return response.json();
  return response.text();
}

function setError(message) {
  elements.loginError.hidden = !message;
  elements.loginError.textContent = message;
}

function statusLabel(status) {
  return { present: "출석", late: "지각", absent: "결석" }[status] || "미제출";
}

function escapeHtml(value) {
  return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#96;");
}
