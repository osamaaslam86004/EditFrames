/**
 * EditFrames Promo Reel Studio JavaScript
 * Interactive event handlers for voiceover previews, custom video dispatch, and video listing.
 */

function updateStatusBanner(message, isLoading = true, isError = false) {
    const banner = document.getElementById('statusBanner');
    const textSpan = document.getElementById('statusText');
    const spinner = document.getElementById('statusSpinner');

    if (!banner || !textSpan || !spinner) return;

    banner.classList.remove('hidden');
    textSpan.textContent = message;

    if (isError) {
        banner.classList.remove('bg-slate-900', 'border-slate-800');
        banner.classList.add('bg-rose-950/80', 'border-rose-800');
        spinner.classList.add('hidden');
    } else {
        banner.classList.remove('bg-rose-950/80', 'border-rose-800');
        banner.classList.add('bg-slate-900', 'border-slate-800');

        if (isLoading) {
            spinner.classList.remove('hidden');
        } else {
            spinner.classList.add('hidden');
            setTimeout(() => {
                banner.classList.add('hidden');
            }, 4000);
        }
    }
}

function getCustomPayload() {
    const titleInput = document.getElementById('customTitle');
    const priceInput = document.getElementById('customPrice');
    const voiceSelect = document.getElementById('voicePersona');
    const aspectSelect = document.getElementById('aspectRatio');
    const imageInput = document.getElementById('imageUrl');

    const product_title = titleInput ? titleInput.value.trim() : 'Wireless Noise-Canceling Headphones';
    const price = priceInput ? parseFloat(priceInput.value) : 129.99;
    const voice_persona = voiceSelect ? voiceSelect.value : 'af_bella';
    const aspect_ratio = aspectSelect ? aspectSelect.value : '9:16';
    const image_url = imageInput ? imageInput.value.trim() : '';

    return {
        product_title: product_title || 'Wireless Noise-Canceling Headphones',
        price: isNaN(price) || price <= 0 ? 129.99 : price,
        image_url: image_url,
        voice_persona: voice_persona,
        aspect_ratio: aspect_ratio,
        use_llm_script: true
    };
}

async function previewAudio() {
    const payload = getCustomPayload();
    updateStatusBanner('Synthesizing preview voiceover (' + payload.voice_persona + ')...', true);

    try {
        const response = await fetch('/api/v1/videos/preview-audio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || 'Server returned HTTP ' + response.status);
        }

        const data = await response.json();
        const audioPlayer = document.getElementById('audioPreviewPlayer');

        if (audioPlayer && data.preview_url) {
            audioPlayer.src = data.preview_url;
            audioPlayer.classList.remove('hidden');
            await audioPlayer.play();
            updateStatusBanner('Voiceover preview ready! Persona: ' + data.voice_persona, false);
        } else {
            throw new Error('Invalid response from preview audio endpoint');
        }
    } catch (err) {
        console.error('Audio preview failed:', err);
        updateStatusBanner('Voiceover preview failed: ' + err.message, false, true);
    }
}

async function triggerCustomGeneration() {
    const payload = getCustomPayload();
    updateStatusBanner('Dispatching custom video job for ' + payload.product_title + '...', true);

    try {
        const response = await fetch('/api/v1/videos/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || 'Server returned HTTP ' + response.status);
        }

        const data = await response.json();
        updateStatusBanner('Video job dispatched! Task ID: ' + data.task_id, false);

        setTimeout(loadVideos, 1500);
    } catch (err) {
        console.error('Custom video generation failed:', err);
        updateStatusBanner('Generation dispatch failed: ' + err.message, false, true);
    }
}

async function triggerBatch() {
    updateStatusBanner('Dispatching batch promo video generation...', true);
    try {
        const response = await fetch('/api/v1/videos/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || 'Server returned HTTP ' + response.status);
        }

        const data = await response.json();
        updateStatusBanner('Batch pipeline dispatched! Task ID: ' + data.task_id, false);

        setTimeout(loadVideos, 2000);
    } catch (err) {
        console.error('Batch generation failed:', err);
        updateStatusBanner('Batch generation failed: ' + err.message, false, true);
    }
}

async function loadVideos() {
    const grid = document.getElementById('videoGrid');
    const countSpan = document.getElementById('videoCount');

    if (!grid) return;

    try {
        const response = await fetch('/api/v1/videos/');
        if (!response.ok) return;

        const data = await response.json();
        const videos = data.videos || [];

        if (countSpan) {
            countSpan.textContent = videos.length + (videos.length === 1 ? ' Reel' : ' Reels');
        }

        if (videos.length === 0) {
            grid.innerHTML = '<div class="col-span-full text-center py-12 bg-slate-900 border border-slate-800 rounded-2xl"><i class="fa-solid fa-film text-4xl text-slate-600 mb-3 block"></i><p class="text-slate-400 font-medium">No promo videos generated yet.</p><p class="text-xs text-slate-500 mt-1">Customize options above and click Generate Custom Reel.</p></div>';
            return;
        }

        grid.innerHTML = videos.map(video => 
            '<div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-lg transition hover:border-slate-700">' +
            '<div class="aspect-[9/16] max-h-[380px] bg-slate-950 relative flex items-center justify-center">' +
            '<video class="w-full h-full object-cover" controls preload="metadata">' +
            '<source src="' + video.download_url + '" type="video/mp4">' +
            'Your browser does not support the video tag.' +
            '</video>' +
            '</div>' +
            '<div class="p-4 flex items-center justify-between border-t border-slate-800 bg-slate-900/90">' +
            '<span class="text-xs font-mono text-slate-400 truncate max-w-[180px]" title="' + video.filename + '">' +
            video.filename +
            '</span>' +
            '<a href="' + video.download_url + '" download="' + video.filename + '" class="inline-flex items-center gap-1.5 text-xs bg-indigo-600/20 text-indigo-400 border border-indigo-500/30 hover:bg-indigo-600 hover:text-white px-3 py-1.5 rounded-lg transition font-medium">' +
            '<i class="fa-solid fa-download"></i> Download' +
            '</a>' +
            '</div>' +
            '</div>'
        ).join('');
    } catch (err) {
        console.error('Failed to load video grid:', err);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadVideos();
});
