import os
import pty
import subprocess
import sys
import select
import termios
import tty

class DobbyCLI:
    def __init__(self, command):
        self.command = command  # Command to be executed (e.g., ssh, telnet)

    def run(self):
        # Create a pseudo-terminal
        # Use master_fd to intercept terminal output
        master_fd, slave_fd = pty.openpty()

        # Start the SSH/Telnet process with the given command
        process = subprocess.Popen(self.command, preexec_fn=os.setsid, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd, shell=True)
        
        # Set the terminal to raw mode
        old_tty = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno())

        try:
            buffer = ""  # Buffer to accumulate the full line of user input

            while True:
                # Check if there's any data to read from the user or the terminal
                rlist, _, _ = select.select([sys.stdin, master_fd], [], [])

                # If the user has typed something
                if sys.stdin in rlist:
                    user_input = sys.stdin.read(1)

                    # Add user input to buffer to accumulate the full line
                    buffer += user_input
                    print(f"\r\nBuffer={repr(buffer)}\r\n")

                    if user_input == '\x03':  # Handle Ctrl-C to exit
                        break
                    
                    # Read full command if the user presses Enter
                    if user_input == '\r':
                        # user_input = sys.stdin.readline()
                        print(f"User typed (full line): {repr(buffer)}")  # Debugging: show full input
                        
                        # Check if the user typed "//" for auto-completion
                        # if "//" in user_input:
                        if "//" in buffer:
                            # Split the command after the "//"
                            request = buffer.split("//", 1)[1].strip()
                            print(f"\r\nIntercepted command for LLM: {request}\r\n")
                            # You'd now send this request to your LLM and handle the response

                            # Clear buffer after handling the line
                            buffer = ""

                            # Instead of sending to the device, you can just intercept here
                            continue

                        # Send the regular input (no "//") to the device
                        os.write(master_fd, buffer.encode())

                        # Clear buffer after sending the line
                        buffer = ""
                        continue

                # If there's output from the terminal (remote device)
                if master_fd in rlist:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    sys.stdout.write(data.decode('utf-8'))
                    sys.stdout.flush()

        finally:
            # Restore the terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
            # Wait for the process to terminate
            process.wait()

# Example usage
if __name__ == "__main__":
    # Use my Elixir-03 for testing
    DobbyCLI("telnet 10.75.221.155 2013").run()