class Message():
  GREEN  = '\033[92m'
  YELLOW = '\033[93m'
  RED    = '\033[91m'
  CLEAR  = '\033[0m'
  
  @staticmethod
  def success(text):
    print(Message.GREEN + '\nSuccess: ' + Message.CLEAR + text)

  @staticmethod
  def warn(text):
    print(Message.YELLOW + '\nWarning: ' + Message.CLEAR + text)
  
  @staticmethod
  def error(text):
    print(Message.RED + '\nError: ' + Message.CLEAR + text)
