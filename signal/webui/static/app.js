"use strict";

const $ = (selector) => document.querySelector(selector);
const state = { token: "", accounts: [], account: "", about: null, groups: [], busy: false, qrTimer: null };
// Resolve relative to the ingress directory; never fetch the HA root /api.
const base = new URL(location.pathname.endsWith("/") ? location.pathname : `${location.pathname}/`, location.origin);
const el = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
function notice(text, error = false) {
  const node = $("#notice");
  node.textContent = text;
  node.className = error ? "error" : "";
  node.hidden = false;
  const dismiss = el("button", "Dismiss", "quiet");
  dismiss.type = "button";
  dismiss.onclick = () => {
    node.hidden = true;
  };
  node.append(document.createTextNode(" "), dismiss);
}
function theme(value) {
  document.documentElement.dataset.theme = value;
  $("#theme").textContent = value === "dark" ? "Light mode" : "Dark mode";
  $("#theme").setAttribute("aria-label", `Switch to ${value === "dark" ? "light" : "dark"} theme`);
  try {
    localStorage.setItem("signal-ui-theme", value);
  } catch {
    /* Storage can be disabled in an iframe. */
  }
}
try {
  theme(localStorage.getItem("signal-ui-theme") === "light" ? "light" : "dark");
} catch {
  theme("dark");
}
$("#theme").onclick = () => theme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

async function api(action, params = {}, data = {}, confirmed = false) {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  const requestId = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  let response;
  try {
    response = await fetch(new URL("api/action", base), {
      method: "POST",
      cache: "no-store",
      redirect: "error",
      headers: { "Content-Type": "application/json", "X-Signal-CSRF": state.token },
      body: JSON.stringify({ action, params, data, confirmed, request_id: requestId }),
      signal: AbortSignal.timeout(100000),
    });
  } catch {
    throw new Error("Connection lost or timed out. The operation may already have succeeded. Check backend state before trying again.");
  }
  let body;
  try {
    body = await response.json();
  } catch {
    throw new Error("Invalid server response. A change may already have succeeded; check before retrying.");
  }
  if (!response.ok) throw new Error(body.error || "Request failed. Check the backend before trying again.");
  return body.result;
}

async function run(work) {
  if (state.busy) return;
  state.busy = true;
  $("#main").setAttribute("aria-busy", "true");
  document.querySelectorAll("button, select").forEach((node) => {
    node.disabled = true;
  });
  // The confirmation dialog is the one interactive surface during an operation.
  $("#confirm")
    .querySelectorAll("button")
    .forEach((node) => {
      node.disabled = false;
    });
  try {
    await work();
  } catch (error) {
    notice(error.message, true);
  } finally {
    state.busy = false;
    $("#main").setAttribute("aria-busy", "false");
    document.querySelectorAll("button, select").forEach((node) => {
      node.disabled = false;
    });
  }
}

function heading(title, description) {
  const main = $("#main");
  main.append(el("span", "SIGNAL / MANAGEMENT", "eyebrow"), el("h1", title), el("p", description, "lead"));
  return main;
}
function card(parent, title, description) {
  const node = el("section", undefined, "card");
  node.append(el("h2", title));
  if (description) node.append(el("p", description, "muted"));
  parent.append(node);
  return node;
}
function button(parent, text, action, quiet = true) {
  const node = el("button", text, quiet ? "quiet" : "");
  node.type = "button";
  node.onclick = () => run(action);
  parent.append(node);
  return node;
}
const labelize = (text) => text.replaceAll("_", " ").replace(/([a-z])([A-Z])/g, "$1 $2");
function values(parent, value) {
  const list = el("dl");
  for (const [key, item] of Object.entries(value || {})) {
    list.append(el("dt", labelize(key)), el("dd", typeof item === "object" ? JSON.stringify(item, null, 2) : String(item)));
  }
  parent.append(list);
}
function records(parent, items, titleKeys = ["name", "number", "id"]) {
  if (!Array.isArray(items)) {
    values(parent, items);
    return;
  }
  if (!items.length) {
    parent.append(el("p", "No entries available yet.", "muted"));
    return;
  }
  for (const item of items) {
    const row = el("div", undefined, "record");
    if (typeof item !== "object" || item === null) row.textContent = String(item);
    else {
      row.append(el("h3", String(titleKeys.map((key) => item[key]).find(Boolean) || "Entry")));
      values(row, item);
    }
    parent.append(row);
  }
}

const f = (name, label, type = "text", required = false, extra = {}) => ({ name, label, type, required, ...extra });
const recipient = () => f("recipient", "Recipient number, UUID, username, or REST group ID", "text", true);
const timer = (name = "expiration_time") => f(name, "Disappearing-message timer (seconds)", "number", false, { help: "Blank: unchanged. 0: turn off disappearing messages." });
const image = () => f("base64_avatar", "Avatar image (optional, up to 2 MiB)", "image");
const permissions = () =>
  ["add_members", "edit_group", "send_messages"].map((key) =>
    f(`permissions.${key}`, `Who can ${labelize(key)}?`, "select", false, { options: ["", "every-member", "only-admins"] }),
  );
const groupFields = () => [
  f("name", "Group name"),
  f("description", "Description", "textarea"),
  timer(),
  f("group_link", "Invite link", "select", false, { options: ["", "disabled", "enabled", "enabled-with-approval"] }),
  ...permissions(),
];

function confirmOperation(title, params, summary) {
  $("#confirm-title").textContent = title;
  $("#confirm-context").textContent = params.account ? `Account: ${params.account}${params.group ? ` · Group: ${params.group}` : ""}` : "Signal account onboarding";
  $("#confirm-summary").textContent = summary || "Apply this operation to the selected account.";
  const dialog = $("#confirm");
  dialog.returnValue = "cancel";
  return new Promise((resolve) => {
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true });
    dialog.showModal();
    dialog.querySelector('[value="cancel"]').focus();
  });
}
async function readFile(file, imageOnly) {
  if (!file || !file.size || file.size > 2 * 1024 * 1024) throw new Error("Choose a nonempty file up to 2 MiB.");
  if (imageOnly && !["image/png", "image/jpeg", "image/webp"].includes(file.type)) throw new Error("Choose a PNG, JPEG, or WebP image.");
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("Cannot read this file."));
    reader.readAsDataURL(file);
  });
}

function form(parent, title, description, action, definitions, options = {}) {
  const panel = card(parent, title, description);
  const formNode = el("form");
  const fieldset = el("div", undefined, "fields");
  const inputs = [];
  for (const definition of definitions) {
    const label = el("label", undefined, "field");
    label.append(el("span", definition.label + (definition.required ? " *" : "")));
    let input;
    if (definition.type === "select" || definition.type === "bool") {
      input = el("select");
      const choices = definition.options || ["", "true", "false"];
      for (const value of choices) {
        const option = el("option", value === "" ? "Unchanged / use default" : value === "true" ? "Yes" : value === "false" ? "No" : labelize(value));
        option.value = value;
        input.append(option);
      }
    } else if (["textarea", "list"].includes(definition.type)) input = el("textarea");
    else {
      input = el("input");
      input.type = ["image", "file"].includes(definition.type) ? "file" : definition.type;
      if (definition.type === "image") input.accept = "image/png,image/jpeg,image/webp";
      if (definition.type === "number") {
        input.min = "0";
        input.step = "1";
        input.max = "9007199254740991";
      }
    }
    input.name = definition.name;
    input.required = definition.required;
    input.autocomplete = "off";
    if (!["file", "image", "select", "bool", "number"].includes(definition.type)) input.maxLength = 10000;
    if (definition.value !== undefined) input.value = definition.value;
    label.append(input);
    if (definition.help || definition.type === "list") label.append(el("span", definition.help || "One entry per line.", "help"));
    fieldset.append(label);
    inputs.push([definition, input]);
  }
  formNode.append(fieldset);
  const submit = el("button", options.submit || title, options.danger ? "danger" : "");
  submit.type = "submit";
  formNode.append(submit);
  const output = el("div", undefined, "result");
  output.hidden = true;
  output.setAttribute("role", "status");
  panel.append(formNode, output);
  formNode.onsubmit = (event) => {
    event.preventDefault();
    run(async () => {
      output.hidden = true;
      try {
        const params = options.params ? options.params() : { account: state.account };
        const data = {};
        const summary = [];
        for (const [definition, input] of inputs) {
          let value = input.value;
          if (["image", "file"].includes(definition.type)) {
            if (!input.files.length) continue;
            value = await readFile(input.files[0], definition.type === "image");
            summary.push(`${definition.label}: ${input.files[0].name}`);
            if (definition.type === "file") value = [value];
          } else {
            if (value === "" && !definition.required) continue;
            if (definition.type === "number") value = Number(value);
            if (definition.type === "bool") value = value === "true";
            if (definition.type === "list")
              value = value
                .split(/\n/)
                .map((item) => item.trim())
                .filter(Boolean);
            summary.push(`${definition.label}: ${definition.type === "password" ? "[hidden]" : Array.isArray(value) ? value.join(", ") : value}`);
          }
          if (definition.name.startsWith("param.")) params[definition.name.slice(6)] = String(value);
          else if (definition.name.startsWith("permissions.")) {
            data.permissions ||= {};
            data.permissions[definition.name.slice(12)] = value;
          } else data[definition.name] = value;
        }
        if (options.transform) options.transform(data);
        if (!(await confirmOperation(title, params, summary.join("\n")))) return;
        const result = await api(action, params, data, true);
        formNode.reset();
        output.replaceChildren(el("p", "Backend accepted the request. This is not proof of delivery or reading."));
        output.className = "result";
        output.hidden = false;
        if (options.success) await options.success(result, output);
        else if (result && !result.ok) values(output, result);
        notice(`${title}: request accepted.`);
      } catch (error) {
        output.textContent = error.message;
        output.className = "result error";
        output.hidden = false;
        notice("Operation failed or is uncertain. Review the message in the form.", true);
      }
    });
  };
  return panel;
}

async function refreshAccounts() {
  const accounts = await api("accounts");
  if (!Array.isArray(accounts) || !accounts.every((item) => typeof item === "string")) throw new Error("Backend returned an invalid account list.");
  state.accounts = accounts;
  if (!accounts.includes(state.account)) state.account = accounts[0] || "";
  const select = $("#account");
  select.replaceChildren();
  if (!accounts.length) select.append(el("option", "No accounts — link a phone to begin"));
  for (const account of accounts) {
    const option = el("option", account);
    option.value = account;
    select.append(option);
  }
  select.value = state.account;
}
function requireAccount(main) {
  if (state.account) return true;
  const node = card(main, "Link your first account", "Choose Link an account to connect your phone or register a dedicated number.");
  node.append(Object.assign(el("a", "Start onboarding →"), { href: "#onboarding" }));
  return false;
}

function overview() {
  const main = heading(
    "Your Signal control room",
    "Link a phone, manage your conversations, and test message sending from one place. Management uses this container’s local REST API.",
  );
  const grid = el("div", undefined, "grid");
  main.append(grid);
  const backend = card(grid, "REST backend", "Connectivity does not establish Signal network health.");
  backend.append(el("div", state.about ? "Connected" : "Unavailable", "metric"));
  if (state.about) values(backend, { mode: state.about.mode, version: state.about.version || state.about.build || "See upstream /about" });
  card(grid, "Linked accounts", "Select an account in the header before making changes.").append(el("div", String(state.accounts.length), "metric"));
  const next = card(main, "A simple setup path", "1. Link or register an account. 2. Select it above. 3. Send a test message. 4. Manage contacts and groups.");
  next.append(Object.assign(el("a", "Link an account →"), { href: "#onboarding" }));
  main.append(
    el(
      "p",
      "This interface never consumes incoming messages. Keep receiving in the Home Assistant integration. For normal/native polling, disable the add-on’s AUTO_RECEIVE setting when another receiver is active.",
      "banner",
    ),
  );
}

function onboarding() {
  const main = heading("Connect your Signal account", "Link your existing phone as the recommended path. Nothing is registered, linked, or sent until you confirm an operation.");
  form(
    main,
    "Link a phone",
    "On your phone, open Signal → Settings → Linked devices, then scan the QR code and approve. Refresh accounts after approval; do not generate another code just to check progress.",
    "link",
    [f("device_name", "Device name", "text", true, { value: "Home Assistant" })],
    {
      params: () => ({}),
      submit: "Generate QR code",
      success: (result, output) => {
        const qr = el("img", undefined, "qr");
        qr.src = `data:image/png;base64,${result.qr}`;
        qr.alt = "Signal device linking QR code";
        output.replaceChildren(qr, el("p", "Scan and approve on your phone. This display expires in five minutes; Signal may expire it earlier."));
        button(output, "I scanned it — refresh accounts", async () => {
          await refreshAccounts();
          notice(
            state.accounts.length
              ? "Account list refreshed. Select your account above, then open Test messages."
              : "No accounts found yet. Complete approval on your phone and refresh again.",
          );
        });
        clearTimeout(state.qrTimer);
        state.qrTimer = setTimeout(() => output.replaceChildren(el("p", "QR display expired. If linking did not finish, generate a new code.")), result.expires_in * 1000);
      },
    },
  );
  const advanced = el("details");
  advanced.append(el("summary", "Advanced: register a dedicated phone number"));
  main.append(advanced);
  advanced.append(
    el(
      "p",
      "Registration makes this backend a primary device and may replace an existing registration. Use linking for your everyday phone. CAPTCHA and registration limits are enforced by Signal.",
      "banner",
    ),
  );
  const accountField = () => f("param.account", "Phone number (international format)", "tel", true);
  form(
    advanced,
    "Request verification code",
    "Request SMS or voice verification. If Signal requires CAPTCHA, complete it externally and paste the signalcaptcha:// token. No external CAPTCHA page is embedded here.",
    "register",
    [accountField(), f("use_voice", "Use voice instead of SMS", "bool"), f("captcha", "CAPTCHA token, if required", "password")],
    { params: () => ({}) },
  );
  form(
    advanced,
    "Verify registration",
    "Enter the code you received and your registration PIN if required.",
    "verify",
    [accountField(), f("param.code", "Verification code", "password", true), f("pin", "Registration PIN", "password")],
    {
      params: () => ({}),
      success: async (_result, output) => {
        await refreshAccounts();
        output.append(el("p", "Accounts refreshed. Select the new account above."));
      },
    },
  );
}

function messages() {
  const main = heading("Test messages", "Send to one explicit destination at a time. No automatic retries, broadcasts, or incoming-message polling.");
  if (!requireAccount(main)) return;
  form(
    main,
    "Send test message",
    "Use a phone number, UUID, username, or REST group ID. For Note to self, use your selected account number.",
    "send",
    [
      recipient(),
      f("message", "Message", "textarea"),
      f("text_mode", "Formatting", "select", false, { options: ["", "normal", "styled"] }),
      f("base64_attachments", "Attachment (optional, up to 2 MiB)", "file"),
      f("quote_timestamp", "Reply to timestamp (optional)", "number"),
      f("quote_author", "Original author for quoted reply"),
      f("edit_timestamp", "Edit your previously sent message (timestamp, optional)", "number"),
    ],
    {
      transform: (data) => {
        data.recipients = [data.recipient];
        delete data.recipient;
        data.message ||= "";
      },
    },
  );
  const grid = el("div", undefined, "grid");
  main.append(grid);
  form(
    grid,
    "Delete a sent message",
    "Request remote deletion of your own message. Signal’s permissions and time limits apply.",
    "delete_message",
    [recipient(), f("timestamp", "Original message timestamp", "number", true)],
    { danger: true },
  );
  form(grid, "Create poll", "Send a poll with 2–10 answers to a direct or group conversation.", "poll", [
    recipient(),
    f("question", "Question", "text", true),
    f("answers", "Answers", "list", true),
    f("allow_multiple_selections", "Allow multiple selections", "bool"),
  ]);
  form(main, "Close poll", "Close a poll created by this account.", "close_poll", [recipient(), f("poll_timestamp", "Poll timestamp", "text", true)]);
  form(main, "Send reaction", "React to a known message using its original author and millisecond timestamp.", "react", [
    recipient(),
    f("target_author", "Original author number or UUID", "text", true),
    f("timestamp", "Original message timestamp", "number", true),
    f("reaction", "Reaction emoji", "text", true),
  ]);
  form(main, "Remove reaction", "Remove your reaction to a known message.", "remove_reaction", [
    recipient(),
    f("target_author", "Original author number or UUID", "text", true),
    f("timestamp", "Original message timestamp", "number", true),
  ]);
}

async function groups() {
  const main = heading("Groups", "Create a group, review members, and manage permissions. Your Signal account must have the required group privileges.");
  if (!requireAccount(main)) return;
  const data = await api("groups", { account: state.account });
  if (!Array.isArray(data)) throw new Error("Invalid group list from backend.");
  state.groups = data;
  const panel = card(main, "Manage an existing group", "Settings left blank remain unchanged. Some current settings are not returned by the backend; no defaults are assumed.");
  const select = el("select", undefined, "group-select");
  select.setAttribute("aria-label", "Select group");
  const empty = el("option", "Select a group…");
  empty.value = "";
  select.append(empty);
  for (const group of data) {
    const option = el("option", `${group.name || "Unnamed group"} · ${group.id}`);
    option.value = group.id;
    select.append(option);
  }
  panel.append(select);
  const detail = el("div");
  panel.append(detail);
  select.onchange = () =>
    run(async () => {
      detail.replaceChildren();
      const groupId = select.value;
      if (!groupId) return;
      const group = await api("group", { account: state.account, group: groupId });
      values(detail, group);
      const params = () => ({ account: state.account, group: groupId });
      form(detail, "Update group", "Edit only the fields you want to change. Avatar uploads are optional.", "update_group", [...groupFields(), image()], { params });
      const membership = el("div", undefined, "grid");
      detail.append(membership);
      for (const [action, title, key] of [
        ["add_members", "Add members", "members"],
        ["remove_members", "Remove members", "members"],
        ["add_admins", "Promote administrators", "admins"],
        ["remove_admins", "Demote administrators", "admins"],
      ]) {
        form(membership, title, "Use international phone numbers or Signal UUIDs, one per line.", action, [f(key, "People", "list", true)], {
          params,
          danger: action.startsWith("remove"),
        });
      }
      form(
        detail,
        "Leave group",
        "This removes your account from the group; it does not delete the group for everyone. Transfer administration first if needed.",
        "leave_group",
        [],
        { params, danger: true },
      );
      form(
        detail,
        "Accept pending invitation",
        "Accept your own invitation to this known group. This is not joining an arbitrary invite URL or approving another person’s join request.",
        "accept_invite",
        [],
        { params },
      );
      form(detail, "Block group", "Blocks the group for this account. Unblocking is not exposed by this REST API; use your Signal client if needed.", "block_group", [], {
        params,
        danger: true,
      });
    });
  form(main, "Create group", "Provide a name and initial members. After creation, refresh this page to manage the new group.", "create_group", [
    f("name", "Group name", "text", true),
    f("members", "Initial members", "list", true),
    ...groupFields().filter((field) => field.name !== "name"),
  ]);
}

async function contacts() {
  const main = heading("Contacts", "Review known contacts and set names or disappearing-message timers.");
  if (!requireAccount(main)) return;
  records(card(main, "Known contacts"), await api("contacts", { account: state.account }), ["name", "profile_name", "number", "uuid"]);
  form(main, "Update contact", "Omitted settings stay unchanged. These operations may depend on primary/linked device support.", "contact", [
    recipient(),
    f("name", "Contact name"),
    timer("expiration_in_seconds"),
  ]);
  form(main, "Sync contacts to linked devices", "Sends this account’s contact list to its linked devices; it does not request a fresh list from your phone.", "sync_contacts", []);
}

async function accountPage() {
  const main = heading("Account & devices", "Manage your Signal presence and linked devices. Primary-account operations may be rejected when this backend is linked to a phone.");
  if (!requireAccount(main)) return;
  const grid = el("div", undefined, "grid");
  main.append(grid);
  form(
    grid,
    "Update profile",
    "Upstream cannot preserve the current avatar when updating a profile without an upload. Upload the desired avatar again, or explicitly approve removing it.",
    "profile",
    [f("name", "Display name", "text", true), f("about", "About", "textarea"), image(), f("remove_avatar", "Remove existing avatar when no image is uploaded", "bool")],
  );
  form(grid, "Update phone privacy", "Blank selections preserve the existing setting. Current privacy values are not returned by this API.", "privacy", [
    f("discoverable_by_number", "Let people find me by phone number", "bool"),
    f("share_number", "Share my phone number", "bool"),
  ]);
  form(grid, "Set username", "Set a nickname or full username with discriminator. The backend returns the resulting username/link.", "username", [
    f("username", "Username", "text", true),
  ]);
  form(grid, "Remove username", "Removes this account’s username.", "remove_username", [], { danger: true });
  const devices = card(main, "Linked devices", "Device 1 is the primary device and cannot be removed here. Removing this backend’s own device disconnects it.");
  try {
    records(devices, await api("devices", { account: state.account }));
  } catch (error) {
    devices.append(el("p", error.message, "error"));
  }
  form(
    main,
    "Link another device",
    "For a primary backend account only. Paste the companion device’s provisioning URI. To link this backend to your phone, use Link an account instead.",
    "add_device",
    [f("uri", "Signal provisioning URI", "password", true)],
  );
  form(
    main,
    "Remove linked device",
    "Verify the device ID in the list above. This immediately revokes that device’s access.",
    "remove_device",
    [f("param.device", "Device ID (greater than 1)", "number", true)],
    { danger: true },
  );
}

async function security() {
  const main = heading(
    "Identity & security",
    "Verify safety numbers through a trusted channel before trusting an identity. This UI does not offer a blanket “trust all keys” action.",
  );
  if (!requireAccount(main)) return;
  const identities = card(main, "Known identities");
  try {
    records(identities, await api("identities", { account: state.account }), ["number", "uuid"]);
  } catch (error) {
    identities.append(el("p", error.message, "error"));
  }
  form(main, "Trust verified identity", "Compare the safety number with your contact outside this interface before confirming.", "trust", [
    f("param.recipient", "Contact number or UUID", "text", true),
    f("verified_safety_number", "Verified 60-digit safety number", "text", true),
  ]);
  const grid = el("div", undefined, "grid");
  main.append(grid);
  form(grid, "Set registration PIN", "Primary accounts only. Keep the PIN securely; it is never saved by this UI.", "pin", [f("pin", "New PIN", "password", true)]);
  form(grid, "Remove registration PIN", "Removes the PIN for this account and reduces its registration protection.", "remove_pin", [], { danger: true });
  form(main, "Resolve rate-limit challenge", "Use a challenge token returned by upstream and a CAPTCHA token obtained through Signal’s external challenge flow.", "challenge", [
    f("challenge_token", "Challenge token", "password", true),
    f("captcha", "CAPTCHA token", "password", true),
  ]);
}

const pages = { overview, onboarding, messages, groups, contacts, account: accountPage, security };
async function render() {
  clearTimeout(state.qrTimer);
  const page = location.hash.slice(1) || "overview";
  $("#main").replaceChildren();
  document.querySelectorAll("nav a").forEach((node) => {
    if (node.hash === `#${page}`) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  });
  try {
    await (pages[page] || overview)();
  } catch (error) {
    $("#main").append(el("p", error.message, "banner error"));
  }
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", () => {
  if (state.busy) {
    notice("An operation is in progress. Use Refresh after it finishes to open the selected page.");
    return;
  }
  run(render);
});
document.addEventListener("click", (event) => {
  if (state.busy && event.target.closest('a[href^="#"]')) {
    event.preventDefault();
    notice("Please wait for the current operation to finish.");
  }
});
$("#account").onchange = () =>
  run(async () => {
    state.account = $("#account").value;
    state.groups = [];
    await render();
  });
$("#refresh").onclick = () =>
  run(async () => {
    state.about = await api("about");
    await refreshAccounts();
    await render();
    notice("Status refreshed.");
  });
run(async () => {
  try {
    const response = await fetch(new URL("session", base), { cache: "no-store", redirect: "error" });
    if (!response.ok) throw new Error("Open this page through Home Assistant ingress.");
    state.token = (await response.json()).token;
    state.about = await api("about");
    await refreshAccounts();
  } catch (error) {
    notice(error.message, true);
  }
  await render();
});
