// Webapps/static/main.js

const video = document.getElementById('camera-feed');
const recordButton = document.getElementById('record-button');
const canvas = document.getElementById('overlay-canvas');
const ctx = canvas.getContext('2d');
const statusDiv = document.getElementById('status-text');
const resultContainer = document.getElementById('result-container');
const resultIframe = document.getElementById('result-iframe');
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
let socket = new WebSocket(WEBSOCKET_URL);

socket.onopen = (event) => { console.log("WebSocket connection established."); };
socket.onclose = (event) => { 
    console.log("WebSocket connection closed. Attempting to reconnect...");
    setTimeout(() => { socket = new WebSocket(WEBSOCKET_URL);  }, 3000); 
 };

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

// --- MODIFIED MESSAGE HANDLER ---
socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.error) {
        statusDiv.innerText = `Error: ${data.error}`;
        return;
    }
    
    // Check for the new "Transcribed" status
    if (data.status === "Transcribed" && data.transcribed_text) {
        // Cache the transcribed text for the "Next Video" button
        currentSession.transcribedText = data.transcribed_text;
        statusDiv.innerText = `Status: Transcribed as "${data.transcribed_text}"`;
        return; // Wait for the next message with the final result
    }

    if (data.status && data.status !== "Done") {
        statusDiv.innerText = `Status: ${data.status}`;
    } else if (data.status === "Done" && data.result.video_url) {
        const videoResult = data.result;
        console.log("Final video result received:", videoResult);
        resultIframe.src = videoResult.embed_url;
        resultContainer.style.display = 'block'; // Show the video container
        statusDiv.innerText = `Showing: ${videoResult.video_title}`;
        
        // Disable record button to prevent accidental state clearing
        recordButton.disabled = true;
        recordButton.style.backgroundColor = 'grey'; 

        currentSession.seenUrls.push(videoResult.video_url);

        //  for testing 
        // alert("Transcription Result:\n\n" + data.result.url);
    }
};

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
                urrentSession.targetObject = null;
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
            recordButton.style.backgroundColor = 'blue';
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
        
        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            if (socket.readyState === WebSocket.OPEN) {
                console.log(`Sending query for '${currentSession.targetObject}'`);

                // Create the metadata object
                const metadata = {
                    target_object: currentSession.targetObject,
                    seen_urls: []   // Always empty for a new audio query
                };

                // Send metadata first, then audio blob
                socket.send(JSON.stringify(metadata));
                socket.send(audioBlob);
            } else {
                alert("Connection to server is not ready.");
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
    resultIframe.src = ''; // Stop the video from playing in the background
    
    // Re-enable the record button so the user can ask a new question
    recordButton.disabled = false;
    recordButton.style.backgroundColor = 'red';
});

// Single entry point
async function init() {
    await startCamera(); 
    await loadModel(); 
    detectionLoop(); 
}
init();


