# Blocknet AIO Monitor

![Blocknet AIO Monitor App](https://raw.githubusercontent.com/tryiou/blocknet_aio_monitor/main/img/blocknet_aio_monitor.png)

Blocknet AIO Monitor is a Python GUI application built with Python 3.10 and tkinter, designed to provide a comprehensive
monitoring and management solution for Blocknet Core, Block-DX, and XLite wallets.

For more information about Blocknet projects, visit:

- [Blocknet Core](https://github.com/blocknetdx/blocknet)
- [Block-DX](https://github.com/blocknetdx/block-dx)
- [XLite](https://github.com/blocknetdx/xlite)
- [Documentation](https://docs.blocknet.org/)

## Features

- **Download Binaries:** Automatically downloads necessary binaries for Blocknet Core, Block-DX, and XLite from the
  official GitHub repository if needed.
- **Download Bootstrap:** Automatically download the Bootstrap for Blocknet Core to facilitate a faster initial sync.
- **Control Panel:** Easily start or close any of the applications from the control panel and monitor their status.
- **Configuration Management:** Check and update configurations for Blocknet Core and Block-DX, ensuring they work
  together seamlessly at first launch.
- **Password Storage:** Securely store existing XLite wallet passwords. Input your password, which will then be
  encrypted and stored in a configuration file for future use.
  On the next XLite startup, the password will be pre-filled and ready to use.
  Right-clicking on this button will clear any stored password.
  Similar functionality will be added for Blocknet Core, enabling automatic wallet unlocking at startup.

## How to use

### From release:

1. Download the release for your OS
   from [Latest Release](https://github.com/tryiou/blocknet_aio_monitor/releases/latest)

2. **Running the application:**

    - **Linux/Windows:**
      Execute the application.

    - **Mac:**
      Mount the dmg file and execute the application.

### From repository:

1. Clone the repository:

     ```bash
     git clone https://github.com/tryiou/blocknet_aio_monitor
     ```
2. Navigate to the repository folder:

     ```bash
     cd blocknet_aio_monitor
     ```

3. Create a virtual environment:

     ```bash
     python -m venv venv
     ```
4. Activate the virtual environment:

    - **Linux/macOS:**

      ```bash
      source venv/bin/activate
      ```

    - **Windows:**

      ```bash
      venv\Scripts\activate
      ```

5. Install requirements:

     ```bash
     pip install -r requirements.txt
     ```

6. Run the GUI:

     ```bash
     python blocknet_aio_monitor.py
     ```

## Contribution

Contributions are welcome! Feel free to submit issues or pull requests.
