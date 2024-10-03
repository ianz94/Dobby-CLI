import os
import pty
import subprocess

class DobbyCLI:
    def __init__(self, command):
        self.command = command  # Command to be executed (e.g., ssh, telnet)
    
    def run(self):
        # Create a pseudo-terminal
        master_fd, slave_fd = pty.openpty()
        
        # Start the SSH/Telnet process with the given command
        process = subprocess.Popen(self.command, preexec_fn=os.setsid, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd, shell=True)
        
        # Read from master_fd to intercept terminal output
        while True:
            try:
                # Read terminal output
                data = os.read(master_fd, 1024)
                if not data:
                    break
                
                # Process and print output (currently just printing raw data)
                print(data.decode('utf-8'), end="")
                
            except OSError:
                break
        
        # Wait for the process to terminate
        process.wait()

# Example usage
if __name__ == "__main__":
    # Use my Elixir-03 for testing
    DobbyCLI("telnet 10.75.221.155 2013").run()
