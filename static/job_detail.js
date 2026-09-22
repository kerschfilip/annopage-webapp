const detailEl = document.getElementById("job-detail");
const jobId = detailEl.dataset.jobId;
const stateEl = document.getElementById("job-state");
const progressFill = document.getElementById("progress-fill");
const errorEl = document.getElementById("job-error");
const logEl = document.getElementById("job-log");
const downloadLink = document.getElementById("download-link");
const processingDetails = document.getElementById("processing-info-details");
const processingEmptyEl = document.getElementById("processing-info-empty");
const processingErrorsEl = document.getElementById("processing-info-errors");
const processingUsageTable = document.getElementById("processing-info-usage");
const processingUsageHead = document.getElementById("processing-info-usage-head");
const processingUsageBody = document.getElementById("processing-info-usage-body");

let timer = null;

function setState(state) {
    stateEl.textContent = state;
    stateEl.className = `state state-${state}`;
}

function renderProcessingInfo(info) {
    if (!info || !info.available) {
        processingDetails.style.display = "none";
        return;
    }
    processingDetails.style.display = "block";

    const errorsByPage = info.errors || {};
    const pageIds = Object.keys(errorsByPage);
    processingErrorsEl.innerHTML = "";
    if (pageIds.length > 0) {
        const list = document.createElement("ul");
        list.className = "error";
        for (const pageId of pageIds) {
            for (const err of errorsByPage[pageId]) {
                const li = document.createElement("li");
                li.textContent = `${pageId} [${err.engine}]: ${err.message}`;
                list.appendChild(li);
            }
        }
        processingErrorsEl.appendChild(list);
    }

    const perEngine = (info.llm_usage && info.llm_usage.per_engine) || {};
    const total = (info.llm_usage && info.llm_usage.total) || {};
    const engineNames = Object.keys(perEngine);

    if (engineNames.length > 0) {
        const columns = [...new Set(engineNames.flatMap((name) => Object.keys(perEngine[name])))];
        processingUsageHead.innerHTML =
            `<tr><th>${I18N["job_detail.usage_engine"]}</th>${columns.map((c) => `<th>${c}</th>`).join("")}</tr>`;
        processingUsageBody.innerHTML = "";
        for (const name of engineNames) {
            const row = document.createElement("tr");
            row.innerHTML = `<td>${name}</td>${columns.map((c) => `<td>${perEngine[name][c] ?? 0}</td>`).join("")}`;
            processingUsageBody.appendChild(row);
        }
        const totalRow = document.createElement("tr");
        totalRow.innerHTML =
            `<td><strong>${I18N["job_detail.usage_total_row"]}</strong></td>${columns.map((c) => `<td>${total[c] ?? 0}</td>`).join("")}`;
        processingUsageBody.appendChild(totalRow);
        processingUsageTable.style.display = "table";
    } else {
        processingUsageTable.style.display = "none";
    }

    processingEmptyEl.style.display = (pageIds.length === 0 && engineNames.length === 0) ? "block" : "none";
}

async function pollJob() {
    const job = await apiFetch(`/api/jobs/${jobId}`);
    setState(job.state);
    progressFill.style.width = `${Math.round((job.progress || 0) * 100)}%`;
    errorEl.textContent = job.error || "";

    if (job.state === "done") {
        downloadLink.style.display = "inline-block";
        clearInterval(timer);
    } else if (job.state === "failed") {
        clearInterval(timer);
    }

    try {
        const logResult = await apiFetch(`/api/jobs/${jobId}/log`);
        logEl.textContent = logResult.log;
    } catch (e) {
        // ignore transient log fetch errors while polling
    }

    try {
        const processingInfo = await apiFetch(`/api/jobs/${jobId}/processing-info`);
        renderProcessingInfo(processingInfo);
    } catch (e) {
        // ignore transient processing-info fetch errors while polling
    }
}

pollJob();
timer = setInterval(pollJob, 2000);
