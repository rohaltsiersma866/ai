function sendMessage() {
    const message = document.getElementById("chatbox").value;
    fetch('/send_message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ input: message })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById("response").innerText = data.response;
    });
}

function uploadFile() {
    const fileInput = document.getElementById("fileInput");
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
    });
}
