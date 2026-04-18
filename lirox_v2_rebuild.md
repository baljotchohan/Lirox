# Lirox v2.0 Production Rebuild Prompt and Implementation Guide

## Overview
This document serves as a comprehensive guide for the production rebuild of Lirox v2.0. It details the requirements, process, and considerations to ensure a seamless transition into the new version.

## Requirements
1. **Hardware Requirements**  
   - Processor: Intel Core i5 or equivalent  
   - RAM: Minimum 8GB  
   - Storage: 100GB free space  
   - Network: Stable internet connection

2. **Software Requirements**  
   - Operating System: Ubuntu 20.04 or later
   - Node.js: v14.x or later  
   - npm: v6.x or later  
   - MongoDB: v4.4 or later  

## Pre-Rebuild Checklist
- [ ] Backup existing data and configurations.
- [ ] Ensure all prerequisites are fulfilled.
- [ ] Notify stakeholders about the scheduled downtime.

## Rebuild Process
1. **Bring down existing services**:
   ```bash
   sudo systemctl stop lirox
   ```  

2. **Clone the repository**:
   ```bash
   git clone https://github.com/baljotchohan/Lirox.git
   cd Lirox
   git checkout v2.0
   ```  

3. **Install dependencies**:
   ```bash
   npm install
   ```  

4. **Run database migrations**:
   ```bash
   npm run migrate
   ```  

5. **Build the application**:
   ```bash
   npm run build
   ```  

6. **Start the services**:
   ```bash
   sudo systemctl start lirox
   ```  

## Post-Rebuild Verification
- Check service status:
   ```bash
   sudo systemctl status lirox
   ```  
- Verify the application is running correctly by accessing the UI through the web browser.

## Troubleshooting
- If the application fails to start, check the logs located in `/var/log/lirox/` for more details.
- Ensure all environment variables are correctly configured.

## Conclusion
Following this guide will ensure a successful rebuild of the Lirox v2.0 production environment, allowing for continued efficient operations and upgraded functionalities.