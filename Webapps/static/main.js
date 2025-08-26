// Webapps/static/main.js

const video = document.getElementById('camera-feed');
const recordButton = document.getElementById('record-button');
const resultVideo = document.getElementById('result-video');

let model = undefined;
let currentTargetObject = null; // This will hold the name of the object we're aiming at
let mediaRecorder;
let audioChunks = [];
let host = window.location.host;

if (host === "") {
    // This handles the case where you open the HTML file directly
    host = "localhost:5000"; 
}
const WEBSOCKET_URL = `ws://${host}/ws/query`;
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
    setInterval(detectObjects, 500); // Run detection every 500ms
}

// Real-Time Detection Loop

async function detectObjects() {
    console.log("Attempting to detect...");
    if (!model || video.readyState < 3) return;

    const predictions = await model.detect(video);

    // Screen center coordinates
    const screenCenterX = window.innerWidth / 2;
    const screenCenterY = window.innerHeight / 2;

    currentTargetObject = null; // Reset target

    for (let prediction of predictions) {
        const [x, y, width, height] = prediction.bbox;
        // Check if the screen center is inside this object's bounding box
        if (screenCenterX > x && screenCenterX < x + width &&
            screenCenterY > y && screenCenterY < y + height) {
            
            currentTargetObject = prediction.class;
            console.log("Current Target:", currentTargetObject);
            break; // Found our target, stop checking
        }
    }
}

// Recording Audio and Calling Backend

// In: static/main.js - REPLACE your existing listeners with these two

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