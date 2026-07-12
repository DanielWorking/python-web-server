import socket
import threading
import os

# --- הגדרות כלליות של השרת ---
HOST = '127.0.0.1'
PORT = 8080
ALLOWED_DIRECTORIES = ['/public', '/images', '/docs']

def send_error(client_socket, status_code, message):
    """
    פונקציית עזר לשליחת הודעות שגיאה (כמו 404 או 400) לדפדפן.
    היא בונה דף HTML קטן שמציג את השגיאה ושולחת אותו.
    """
    # יצירת גוף ההודעה (HTML בסיסי)
    body = f"<html><body><h1>{status_code} {message}</h1></body></html>".encode('utf-8')
    
    # בניית הכותרות של התגובה לפי תקן HTTP/1.0
    response = f"HTTP/1.0 {status_code} {message}\r\n".encode('utf-8')
    response += f"Content-Length: {len(body)}\r\n".encode('utf-8')
    response += b"Content-Type: text/html\r\n\r\n" # שורת רווח כפולה חובה בסוף הכותרות
    response += body # הוספת התוכן עצמו
    
    client_socket.sendall(response)

def handle_client(client_socket, client_address):
    """
    פונקציה זו מטפלת בלקוח בודד (רצה בתהליכון נפרד).
    """
    print(f"[NEW CONNECTION] Connected to {client_address}")
    
    try:
        request_data = b"" 
        
        # קריאת הנתונים מהרשת עד למציאת סוף הכותרות
        while b"\r\n\r\n" not in request_data:
            chunk = client_socket.recv(1024)
            if not chunk:
                break
            request_data += chunk
        
        if request_data:
            decoded_request = request_data.decode('utf-8')
            lines = decoded_request.split('\r\n')
            request_line = lines[0]
            parts = request_line.split(' ')
            
            # פענוח הבקשה (Method, Path, Version)
            if len(parts) == 3:
                method = parts[0]
                path = parts[1]
                
                # מוודאים שמדובר בבקשת GET בלבד
                if method != 'GET':
                    send_error(client_socket, 400, "Bad Request")
                    return
                    
                #  אבטחה - חסימת ניסיון לחציית ספריות
                if ".." in path:
                    send_error(client_socket, 400, "Bad Request")
                    return
                    
                # אבטחה - אימות מול הספריות המורשות
                is_allowed = False
                if path == '/' or path.count('/') == 1:
                    is_allowed = True
                else:
                    for allowed_dir in ALLOWED_DIRECTORIES:
                        if path.startswith(allowed_dir + '/'):
                            is_allowed = True
                            break
                
                # אם הספריה לא מורשית, נחזיר שגיאת 403 (Forbidden)        
                if not is_allowed:
                    send_error(client_socket, 403, "Forbidden")
                    return

                # --- קריאת הקובץ והחזרת התגובה ---
                
                # אם המשתמש הקיש רק את הכתובת הראשית, נפנה אותו לקובץ index.html
                if path == '/':
                    path = '/index.html'
                
                # הסרת הלוכסן (/) הראשון כדי שהנתיב יעבוד טוב במערכת ההפעלה
                file_path = path.lstrip('/')
                
                try:
                    # מנסים לפתוח את הקובץ לקריאה בינארית ('rb')
                    with open(file_path, 'rb') as file:
                        file_data = file.read()
                        
                    # זיהוי סוג הקובץ (MIME Type) כדי שהדפדפן ידע איך להציג אותו
                    content_type = "text/plain"
                    if file_path.endswith('.html'):
                        content_type = "text/html"
                    elif file_path.endswith('.css'):
                        content_type = "text/css"
                    elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
                        content_type = "image/jpeg"
                    elif file_path.endswith('.png'):
                        content_type = "image/png"
                    
                    # בניית התגובה המוצלחת (200 OK)
                    response = b"HTTP/1.0 200 OK\r\n"
                    response += f"Content-Length: {len(file_data)}\r\n".encode('utf-8')
                    response += f"Content-Type: {content_type}\r\n".encode('utf-8')
                    response += b"\r\n" # שורת רווח חובה המפרידה בין הכותרות לתוכן
                    response += file_data # צירוף הקובץ עצמו
                    
                    # שליחת התגובה כולה בחזרה ללקוח
                    client_socket.sendall(response)
                    print(f"[SUCCESS] Served {path} to {client_address}")
                    
                except FileNotFoundError:
                    # אם הקובץ לא נמצא במחשב, נחזיר שגיאת 404
                    send_error(client_socket, 404, "Not Found")
                    print(f"[ERROR] 404 Not Found: {path}")
                    
            else:
                send_error(client_socket, 400, "Bad Request")
                
    except Exception as e:
        print(f"[ERROR] Connection closed with error: {e}")
    finally:
        # חובה לסגור את החיבור בסיום ללא קשר לתוצאה (Stateless)
        client_socket.close()

def start_server():
    """
    הפונקציה הראשית שמפעילה את השרת
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"[LISTENING] Server is listening on http://{HOST}:{PORT}")
    
    try:
        while True:
            client_socket, client_address = server_socket.accept()
            # יצירת תהליכון לכל לקוח כדי שלא יעכבו אחד את השני
            thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
            thread.start()
    except KeyboardInterrupt:
        print("\n[SERVER STOPPED] Shutting down...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()