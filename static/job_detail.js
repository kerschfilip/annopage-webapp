const detailEl = document.getElementById("job-detail");
const jobId = detailEl.dataset.jobId;
const stateEl = document.getElementById("job-state");
const progressFill = document.getElementById("progress-fill");
const errorEl = document.getElementById("job-error");
const logEl = document.getElementById("job-log");
const downloadLink = document.getElementById("download-link");

let timer = null;

function setState(state) {
    stateEl.textContent = state;
    stateEl.className = `state state-${state}`;
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
}

pollJob();
timer = setInterval(pollJob, 2000);
