const inspectBtn = document.getElementById("inspect-btn");
const inspectResult = document.getElementById("inspect-result");
const inputPathField = document.getElementById("input_path");
const inputPicker = document.getElementById("input-picker");
const targetSelect = document.getElementById("target_id");
const engineSelect = document.getElementById("engine_name");
const form = document.getElementById("job-form");

async function inspectPath(path) {
    inputPathField.value = path;
    inspectResult.textContent = "Ověřuji...";
    try {
        const result = await apiFetch("/api/input/inspect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path }),
        });
        if (result.ok) {
            inspectResult.innerHTML = `<p class="notice">OK — ${result.images_count} obrázků` +
                (result.alto_dir ? `, ALTO: ${result.alto_count} souborů` : ", bez ALTO") +
                (result.metadata_path ? `, metadata.json: ${result.metadata_count ?? "?"} záznamů` : ", bez metadata.json") +
                `</p>`;
        } else {
            inspectResult.innerHTML = `<p class="error">${result.errors.join("<br>")}</p>`;
        }
    } catch (e) {
        inspectResult.innerHTML = `<p class="error">${e.message}</p>`;
    }
}

async function loadInputPicker() {
    try {
        const result = await apiFetch("/api/input/browse");
        if (!result.available || result.candidates.length === 0) return;

        const select = document.createElement("select");
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.textContent = `-- vybrat z ${result.root} (${result.candidates.length}) --`;
        select.appendChild(placeholder);

        for (const c of result.candidates) {
            const opt = document.createElement("option");
            opt.value = c.path;
            const flags = [`${c.images_count} obr.`, c.has_alto ? "ALTO" : null, c.has_metadata ? "metadata" : null]
                .filter(Boolean).join(", ");
            opt.textContent = `${c.relative_path} (${flags})`;
            select.appendChild(opt);
        }

        select.addEventListener("change", () => {
            if (select.value) inspectPath(select.value);
        });
        inputPicker.appendChild(select);
    } catch (e) {
        console.error(e);
    }
}

loadInputPicker();

inspectBtn.addEventListener("click", () => inspectPath(inputPathField.value.trim()));

const engineDescriptionEl = document.getElementById("engine-description");
let engineDescriptions = {};

targetSelect.addEventListener("change", async () => {
    engineSelect.innerHTML = '<option value="">-- výchozí --</option>';
    engineDescriptions = {};
    engineDescriptionEl.style.display = "none";
    if (!targetSelect.value) return;
    try {
        const result = await apiFetch(`/api/engines?target_id=${encodeURIComponent(targetSelect.value)}`);
        for (const engine of result.engines) {
            const opt = document.createElement("option");
            opt.value = engine.name;
            opt.textContent = engine.name;
            engineSelect.appendChild(opt);
            engineDescriptions[engine.name] = engine.description;
        }
        if (result.error) {
            const opt = document.createElement("option");
            opt.disabled = true;
            opt.textContent = `Nelze načíst engine: ${result.error}`;
            engineSelect.appendChild(opt);
        }
    } catch (e) {
        console.error(e);
    }
});

engineSelect.addEventListener("change", () => {
    const description = engineDescriptions[engineSelect.value];
    if (description) {
        engineDescriptionEl.textContent = description;
        engineDescriptionEl.style.display = "block";
    } else {
        engineDescriptionEl.style.display = "none";
    }
});

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const body = {
        input_path: inputPathField.value.trim(),
        target_id: targetSelect.value,
        engine_name: engineSelect.value,
        captioning_profile_id: document.getElementById("captioning_profile_id").value || null,
        output_path: document.getElementById("output_path").value.trim(),
        outputs: {
            alto: data.has("output_alto"),
            embeddings: data.has("output_embeddings"),
            embeddings_jsonlines: data.has("output_embeddings_jsonlines"),
            renders: data.has("output_renders"),
            crops: data.has("output_crops"),
            image_captioning_prompts: data.has("output_image_captioning_prompts"),
        },
    };
    try {
        const job = await apiFetch("/api/jobs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        window.location.href = `/jobs/${job.id}`;
    } catch (e) {
        alert(`Nepodařilo se spustit úlohu: ${e.message}`);
    }
});
