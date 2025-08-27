// Webapps/static/main.js

const video = document.getElementById('camera-feed');
const recordButton = document.getElementById('record-button');
const resultVideo = document.getElementById('result-video');
const canvas = document.getElementById('overlay-canvas');
const ctx = canvas.getContext('2d');

let model = undefined;
let currentTargetObject = null; // This will hold the name of the object we're aiming at
let mediaRecorder;
let audioChunks = [];
let host = window.location.host;
if (host === "") {
    host = "localhost:5000"; 
}

// Check if the current page is loaded over HTTPS
const isSecure = window.location.protocol === 'https:';

// Use 'wss://' for secure connections, 'ws://' for insecure ones
const protocol = isSecure ? 'wss' : 'ws';

const WEBSOCKET_URL = `${protocol}://${host}/ws/query`;
console.log("Attempting to connect WebSocket to:", WEBSOCKET_URL);

let socket = new WebSocket(WEBSOCKET_URL);

socket.onopen = (event) => {
    console.log("WebSocket connection established.");
};

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.error) {
        console.error("Error from server:", data.error);
        alert(`Error: ${data.error}`);
    } else if (data.status && data.status !== "Done") {
        console.log("Status update:", data.status);
        // You could display this status on the UI here
    } else if (data.status === "Done" && data.result.url) {
        console.log("Final result received:", data.result);

        // --- TEMPORARY CHANGE FOR TESTING ---
        // Instead of trying to play a video, we will show an alert
        // with the transcribed text that we received in the 'url' field.
        alert("Transcription Result:\n\n" + data.result.url);

        // resultVideo.src = data.result.url;
        // resultVideo.style.display = 'block';
        // resultVideo.play();
    }
};

socket.onclose = (event) => {
    console.log("WebSocket connection closed. Attempting to reconnect...");
    // Simple reconnect logic
    setTimeout(() => { socket = new WebSocket(WEBSOCKET_URL); }, 3000);
};

// 1. Start the camera
async function startCamera() {
    const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' }
    });
    video.srcObject = stream;
    await video.play();
}

// 2. Load the object detection model
async function loadModel() {
    model = await cocoSsd.load();
    console.log("Model loaded!");
    // Start detecting objects continuously
    setInterval(detectionLoop, 500); // Run detection every 500ms
}

// Real-Time Detection Loop

async function detectionLoop() {
    if (model && video.readyState >= 3) {
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
                    
                    currentTargetObject = prediction.class;
                    objectFound = true;
                }
            }
            if (!objectFound) {
                currentTargetObject = null;
            }
            // Update the status text on the UI
            const statusDiv = document.getElementById('status-text');
            if (currentTargetObject) {
                statusDiv.innerText = `Target: ${currentTargetObject}`;
                statusDiv.style.color = 'lime'; // Green
            } else {
                statusDiv.innerText = `Status: Aim at a recognized object`;
                statusDiv.style.color = 'yellow'; // Yellow
            }
        }
    }
    requestAnimationFrame(detectionLoop);
}

// Recording Audio and Calling Backend

recordButton.addEventListener('mousedown', () => {
    // Log the state AT THE MOMENT OF THE CLICK
    console.log(`Mousedown event: currentTargetObject is '${currentTargetObject}'`);

    if (!currentTargetObject) {
        alert("Please point the camera at an object first.");
        return; // Stop execution
    }

    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            console.log("Microphone access granted. Starting recorder.");
            audioChunks = []; // Clear previous recording chunks
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
    // Check if mediaRecorder was successfully created before trying to stop it
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        recordButton.style.backgroundColor = 'red';

        mediaRecorder.onstop = () => { // onstop should be defined inside mouseup
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });

            if (socket.readyState === WebSocket.OPEN) {
                console.log(`Sending query for '${currentTargetObject}' via WebSocket...`);
                socket.send(currentTargetObject);
                socket.send(audioBlob);
            } else {
                alert("Connection to server is not ready. Please wait.");
            }
        };
    }
});

// call the functions to start everything
startCamera();
loadModel();