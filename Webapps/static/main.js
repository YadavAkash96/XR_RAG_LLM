// Webapps/static/main.js

const video = document.getElementById('camera-feed');
const recordButton = document.getElementById('record-button');
const canvas = document.getElementById('overlay-canvas');
const ctx = canvas.getContext('2d');
const statusDiv = document.getElementById('status-text');
const resultContainer = document.getElementById('result-container');
const playerContent = document.getElementById('player-content');
const nextVideoButton = document.getElementById('next-video-button');
const closeVideoButton = document.getElementById('close-video-button');

let model = undefined;
let mediaRecorder;
let audioChunks = [];

// State management for the current session
const currentSession = {
    targetObject: null,  // cross hair pointing at
    transcribedText: null, // last transcribed question
    seenUrls: [] // in current session video already shown
};

// --- WebSocket Setup (mostly unchanged) ---
const host = window.location.host || "localhost:5000";
const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
const WEBSOCKET_URL = `${protocol}://${host}/ws/query`;
let socket;

function connectWebSocket() {
    console.log("Attempting to connect WebSocket...");
    socket = new WebSocket(WEBSOCKET_URL);

    socket.onopen = (event) => {
        console.log("WebSocket connection established.");
        statusDiv.innerText = "Status: Aim at a recognized object";
        statusDiv.style.color = 'yellow';
    };

    socket.onmessage = (event) => {
        console.log("--- Message received from server! ---");
        const data = JSON.parse(event.data);
        
        if (data.error) {
            statusDiv.innerText = `Error: ${data.error}`;
            recordButton.disabled = false;
            recordButton.style.backgroundColor = 'red';
            return;
        }
        if (data.status === "Transcribed" && data.transcribed_text) {
            currentSession.transcribedText = data.transcribed_text;
            statusDiv.innerText = `Status: Transcribed as "${data.transcribed_text}"`;
            return;
        }
        if (data.status && data.status !== "Done") {
            statusDiv.innerText = `Status: ${data.status}`;
        } else if (data.status === "Done" && data.result && data.result.video_url) {
            handleFinalResult(data.result);
        }
    };

    socket.onclose = (event) => {
        console.log("WebSocket connection closed. Reconnecting in 3 seconds...");
        statusDiv.innerText = "Status: Reconnecting...";
        statusDiv.style.color = 'orange';
        setTimeout(connectWebSocket, 3000); 
    };

    socket.onerror = (error) => {
        console.error("WebSocket error observed:", error);
        // onclose will be called automatically after an error.
    };
}

async function startCamera() {
    const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
    });
    video.srcObject = stream;
    await video.play();
}

async function loadModel() {
    model = await cocoSsd.load();
    console.log("Model loaded!");
    // Start detecting objects continuously
    // setInterval(detectionLoop, 500); // Run detection every 500ms
}


// --- NEW FUNCTION: Function to handle redirected videos/shorts from App ---
async function handleFinalResult(videoData) {
    console.log("Final video result received:", videoData);
    
    const playerContent = document.getElementById('player-content');
    if (!playerContent) {
        console.error("Critical Error: #player-content div not found in HTML!");
        return;
    }
    playerContent.innerHTML = '';
    try
    {
        if (videoData.platform === "YouTube" && videoData.embed_url) {
            console.log("Displaying YouTube iframe player.");
            const iframe = document.createElement('iframe');
            iframe.src = videoData.embed_url;
            iframe.allow = "autoplay; encrypted-media";
            iframe.allowFullscreen = true;
            iframe.style.width = '100%';
            iframe.style.height = '200px';
            iframe.style.border = 'none';
            playerContent.appendChild(iframe);

        } else if (videoData.platform === "TikTok" || videoData.platform === "Instagram") {
            console.log(`Attempting to display clickable thumbnail for ${videoData.platform}.`);
            // TikTok/Instagram Flow with oEmbed
            let stableThumbnailUrl = null;

            if (videoData.platform === "TikTok") {
                const oEmbedUrl = `https://www.tiktok.com/oembed?url=${encodeURIComponent(videoData.video_url)}`;
                const response = await fetch(oEmbedUrl);
                if (!response.ok) 
                {
                    throw new Error(`TikTok oEmbed API failed with status: ${response.status}`);
                }
                const oEmbedData = await response.json();
                stableThumbnailUrl = oEmbedData.thumbnail_url;
                console.log("Successfully fetched stable thumbnail:", stableThumbnailUrl);
            }
            else 
            {
                stableThumbnailUrl = videoData.thumbnail_url;
            }
                
            if (!stableThumbnailUrl) { throw new Error("No thumbnail could be found."); }

            const thumbnailLink = document.createElement('a');
            thumbnailLink.href = videoData.video_url;
            thumbnailLink.target = '_blank';
            
            const thumbnailImage = document.createElement('img');
            thumbnailImage.src = stableThumbnailUrl;
            thumbnailImage.style.width = '100%';
            thumbnailImage.style.height = '200px';
            thumbnailImage.style.objectFit = 'cover';
            thumbnailImage.style.cursor = 'pointer';
            thumbnailImage.alt = `Thumbnail for ${videoData.video_title}`;
            
            thumbnailLink.appendChild(thumbnailImage);
            playerContent.appendChild(thumbnailLink);
        }
        else 
        {
            // Fallback for unknown platforms
            throw new Error(`Unknown platform type: ${videoData.platform}`);
        }

        // --- Update UI and State (Common to all results) ---
        resultContainer.style.display = 'block';
        statusDiv.innerText = `Showing: ${videoData.video_title}`;
        recordButton.disabled = true;
        recordButton.style.backgroundColor = 'grey';
        currentSession.seenUrls.push(videoData.video_url);
    }
    catch (error) {
        console.error("Failed to display video result:", error);
        statusDiv.innerText = `Error: Could not display video. ${error.message}`;
        // On display error, make sure the user can try again.
        recordButton.disabled = false;
        recordButton.style.backgroundColor = 'red';
    }
}



// Real-Time Detection Loop
async function detectionLoop() {
    if (model && video.readyState >= 3 && resultContainer.style.display !== 'block') {
        // Get the video's intrinsic size vs its display size
        const videoWidth = video.videoWidth;
        const videoHeight = video.videoHeight;
        const displayWidth = video.clientWidth;
        const displayHeight = video.clientHeight;

        // Ensure we don't divide by zero before the video is fully initialized
        if (videoWidth > 0 && videoHeight > 0) {
            // Calculate the scale factor
            const scaleX = displayWidth / videoWidth;
            const scaleY = displayHeight / videoHeight;

            // Get predictions
            const predictions = await model.detect(video);

            // Match canvas size to video element size
            canvas.width = displayWidth;
            canvas.height = displayHeight;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const screenCenterX = canvas.width / 2;
            const screenCenterY = canvas.height / 2;
            let objectFound = false;

            for (let prediction of predictions) {
                // Scale the bounding box coordinates to the display size
                const scaledX = prediction.bbox[0] * scaleX;
                const scaledY = prediction.bbox[1] * scaleY;
                const scaledWidth = prediction.bbox[2] * scaleX;
                const scaledHeight = prediction.bbox[3] * scaleY;

                // Draw the scaled bounding box
                ctx.strokeStyle = '#00FFFF'; // Bright cyan color
                ctx.lineWidth = 4; // Make it thicker for mobile
                ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

                // Draw the label
                ctx.fillStyle = '#00FFFF';
                ctx.font = '24px Arial'; // Make it bigger for mobile
                ctx.fillText(
                    `${prediction.class} (${Math.round(prediction.score * 100)}%)`,
                    scaledX,
                    scaledY > 30 ? scaledY - 10 : 30 // Adjust label position
                );

                // Check if this object is under the crosshair
                if (!objectFound && screenCenterX > scaledX && screenCenterX < scaledX + scaledWidth &&
                    screenCenterY > scaledY && screenCenterY < scaledY + scaledHeight) {
                    
                    currentSession.targetObject = prediction.class;
                    objectFound = true;
                }
            }
            if (!objectFound) {
                currentSession.targetObject = null;
            }
            // Update the status text on the UI
            const statusDiv = document.getElementById('status-text');
            if (currentSession.targetObject) {
                statusDiv.innerText = `Target: ${currentSession.targetObject}`;
                statusDiv.style.color = 'lime';
            } else {
                statusDiv.innerText = `Status: Aim at a recognized object`;
                statusDiv.style.color = 'yellow';
            }
        }
    }
    requestAnimationFrame(detectionLoop);
}

// --- MODIFIED Recording Logic ---
recordButton.addEventListener('mousedown', () => {
    // --- THIS IS THE NEW ROBUST LOGIC ---
    let targetForQuery = currentSession.targetObject;

    // Fallback: If the variable is null, try to get the target from the UI text
    if (!targetForQuery && statusDiv.innerText.startsWith("Target:")) {
        targetForQuery = statusDiv.innerText.replace("Target: ", "").trim();
        console.log(`Race condition workaround: Got target '${targetForQuery}' from UI text.`);
    }

    if (!targetForQuery) {
        alert("Please point the camera at an object first.");
        return; // Stop execution
    }


    // Now, we can proceed with confidence using targetForQuery
    console.log(`Mousedown event: Confirmed target is '${targetForQuery}'`);
    currentSession.targetObject = targetForQuery; 
    // Reset the session state for a new query
    currentSession.seenUrls = [];
    currentSession.transcribedText = null;
    resultContainer.style.display = 'none';

    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            console.log("Microphone access granted. Starting recorder.");
            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };
            mediaRecorder.start();
            recordButton.style.backgroundColor = 'blue'; // Indicate recording is active
        })
        .catch(error => {
            console.error("Error getting microphone access:", error);
            alert("Could not access microphone. Please check permissions.");
        });
});

recordButton.addEventListener('mouseup', () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        // recordButton.style.backgroundColor = 'red';  We don't change the color back here, the 'close' button will
        
        // Change the button to a "processing" state immediately on release.
        recordButton.style.backgroundColor = 'grey';
        recordButton.disabled = true; // Disable it to prevent double-clicks

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
             
            if (audioBlob.size === 0) {
                console.warn("Empty audio recorded. Not sending to server.");
                statusDiv.innerText = "No audio detected. Please try again.";
                recordButton.disabled = false;
                recordButton.style.backgroundColor = 'red';
                return; 
            }

            if (socket.readyState === WebSocket.OPEN) {
                console.log(`Sending query for '${currentSession.targetObject}'`);

                const metadata = {
                    target_object: currentSession.targetObject,
                    seen_urls: []   
                };

                // Send metadata first, then audio blob
                socket.send(JSON.stringify(metadata));
                socket.send(audioBlob);
            } 
            else 
            {
                alert("Connection to server is not ready.");
                recordButton.disabled = false;
                recordButton.style.backgroundColor = 'red';
            }
        };
    }
});

// --- "Show Me Another" Logic ---
nextVideoButton.addEventListener('click', () => {
    if (!currentSession.targetObject || !currentSession.transcribedText) {
        alert("Session lost or no initial query made. Please ask a new question.");
        return;
    }

    if (socket.readyState === WebSocket.OPEN) {
        console.log(`Requesting next video for '${currentSession.targetObject}', excluding ${currentSession.seenUrls.length} videos.`);

        // Create the metadata for a "Next Video" request
        const metadata = {
            target_object: currentSession.targetObject,
            seen_urls: currentSession.seenUrls,
            transcribed_text: currentSession.transcribedText // Include the cached text
        };

        // Send ONLY the JSON message. No audio blob follows.
        socket.send(JSON.stringify(metadata));
        statusDiv.innerText = "Finding another video...";

    } else {
        alert("Connection to server is not ready.");
    }
});

closeVideoButton.addEventListener('click', () => {
    resultContainer.style.display = 'none'; // Hide the video
    if (playerContent) {
        playerContent.innerHTML = ''; 
    }
    // Re-enable the record button so the user can ask a new question
    recordButton.disabled = false;
    recordButton.style.backgroundColor = 'red';
});


async function init() {
    await startCamera(); 
    await loadModel(); 
    detectionLoop(); 
    connectWebSocket(); 
}

// Start everything
init();
