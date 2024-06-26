import logging
import socket
from shared.stream import Stream

class SocketConnectionHandler:
    
    def __init__(self, sock: socket.socket):
        self._stream = Stream(sock)
        self.host, _ = sock.getpeername()

    @classmethod
    def create_from_socket(cls, sock: socket.socket):
        return cls(sock)
    
    @classmethod
    def connect_and_create(cls, host: str, port: int, timeout: int = None):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        if timeout:
            sock.settimeout(timeout)
        return cls(sock)

        
    def send_message(self, message: str):
        """
        Sends a message to the client stream. With the lenght of the message in the first 4 bytes.
        """
        message = message.encode('utf-8')
        size_of_message = len(message)
        self._stream.send(int(size_of_message).to_bytes(4, byteorder='big'))
        self._stream.send(message)
        
        
    def read_message_raw(self):
        """
        Reads a message from the client stream. Returns the raw bytes read.
        """
        try: 
            size_of_message = int.from_bytes(self._stream.recv(4), byteorder='big')
            message = self._stream.recv(size_of_message)
        except OSError as e:
            logging.error(f"action: read_message_size | result: fail | error: {e}")
            raise OSError("Socket connection broken")
        return message


    def read_message(self):
        """
        Reads a message from the client stream and decodes it.
        """
        return self.read_message_raw().decode('utf-8')
    
    

        
    def read_message_with_size_in_lines(self):
        """
        Reads a message from the client stream.
        """
        try: 
            size_of_message = int.from_bytes(self._stream.recv(4), byteorder='big')
            message = self._stream.recv(size_of_message).decode('utf-8')
            size_in_lines = message.count("\n")
        except OSError as e:
            logging.error(f"action: read_message_size | result: fail | error: {e}")
            raise OSError("Socket connection broken")
        return message, size_in_lines
        
        
    def close(self):
        self._stream.close()