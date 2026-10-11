async function loadVideos() {
  const grid = document.getElementById("videoGrid");
  const countLabel = document.getElementById("videoCount");

  try {
    const res = await fetch("/api/videos");
    const data = await res.json();

    countLabel.innerText = `${data.count} Reels`;
    grid.innerHTML = "";

    if (data.count === 0) {
      grid.innerHTML = `
            <div class="col-span-full text-center py-20 border-2 border-dashed border-slate-800 rounded-2xl">
              <i class="fa-solid fa-film text-4xl text-slate-600 mb-3"></i>
              <p class="text-slate-400">No promo videos generated yet.</p>
              <p class="text-slate-500 text-sm mt-1">Click "Generate Now" or wait for weekly cron run.</p>
            </div>`;
      return;
    }

    data.videos.forEach((video) => {
      const card = document.createElement("div");
      card.className =
        "bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl flex flex-col";
      card.innerHTML = `
            <div class="relative aspect-[9/16] bg-black">
              <video src="${video.download_url}" controls class="w-full h-full object-cover"></video>
            </div>
            <div class="p-5 flex justify-between items-center bg-slate-900">
              <span class="text-sm font-semibold text-slate-300 font-mono">${video.filename}</span>
              <a href="${video.download_url}" download class="bg-slate-800 hover:bg-slate-700 text-cyan-400 p-3 rounded-lg transition border border-slate-700">
                <i class="fa-solid fa-download"></i>
              </a>
            </div>
          `;
      grid.appendChild(card);
    });
  } catch (err) {
    console.error("Failed to load videos:", err);
  }
}

async function triggerBatch() {
  const btn = document.getElementById("generateBtn");
  const banner = document.getElementById("statusBanner");
  const statusText = document.getElementById("statusText");

  btn.disabled = true;
  btn.classList.add("opacity-50", "cursor-not-allowed");
  banner.classList.remove("hidden");
  statusText.innerText = "Generating new promo reels... Please wait.";

  try {
    const res = await fetch("/api/generate-now", { method: "POST" });
    if (res.ok) {
      statusText.innerText = "Success! New videos generated.";
      setTimeout(() => banner.classList.add("hidden"), 3000);
      await loadVideos();
    } else {
      statusText.innerText = "Error generating videos.";
    }
  } catch (err) {
    statusText.innerText = "Server error occurred.";
  } finally {
    btn.disabled = false;
    btn.classList.remove("opacity-50", "cursor-not-allowed");
  }
}

// Load initial videos on page load
loadVideos();
