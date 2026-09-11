const targetForm = document.getElementById("target-form");
const targetsTable = document.getElementById("targets-table");
const profileForm = document.getElementById("profile-form");
const profilesTable = document.getElementById("profiles-table");

targetForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(targetForm));
    try {
        const target = await apiFetch("/api/targets", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data),
        });
        const row = document.createElement("tr");
        row.dataset.id = target.id;
        row.innerHTML = `<td>${target.label}</td><td>${target.api_url}</td><td><code>${target.api_key}</code></td>
            <td><button class="delete-target" data-id="${target.id}">${I18N["common.delete"]}</button></td>`;
        targetsTable.appendChild(row);
        targetForm.reset();
    } catch (e) {
        alert(`${I18N["settings.add_target_failed"]}: ${e.message}`);
    }
});

targetsTable.addEventListener("click", async (event) => {
    if (!event.target.classList.contains("delete-target")) return;
    const id = event.target.dataset.id;
    await apiFetch(`/api/targets/${id}`, { method: "DELETE" });
    event.target.closest("tr").remove();
});

profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(profileForm));
    let settings;
    try {
        settings = JSON.parse(data.settings);
    } catch (e) {
        alert(I18N["settings.invalid_json"]);
        return;
    }
    try {
        const profile = await apiFetch("/api/captioning-profiles", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ label: data.label, settings }),
        });
        const row = document.createElement("tr");
        row.dataset.id = profile.id;
        row.innerHTML = `<td>${profile.label}</td><td><button class="delete-profile" data-id="${profile.id}">${I18N["common.delete"]}</button></td>`;
        profilesTable.appendChild(row);
        profileForm.reset();
    } catch (e) {
        alert(`${I18N["settings.add_profile_failed"]}: ${e.message}`);
    }
});

profilesTable.addEventListener("click", async (event) => {
    if (!event.target.classList.contains("delete-profile")) return;
    const id = event.target.dataset.id;
    await apiFetch(`/api/captioning-profiles/${id}`, { method: "DELETE" });
    event.target.closest("tr").remove();
});
