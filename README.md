# Bambu Lab - Spaghetti Detection Integration

Upgrade your Bambu Lab 3D printer experience with the Home Assistant Spaghetti Detection Integration. This
integration leverages the power of both the [Bambu Lab Integration](https://github.com/greghesp/ha-bambulab) and
the [Obico](https://www.obico.io) ML server, providing a solution for detecting and handling spaghetti incidents during
your prints.

> This repository is a security-hardened fork of
> [nberktumer/ha-bambu-lab-p1-spaghetti-detection](https://github.com/nberktumer/ha-bambu-lab-p1-spaghetti-detection).
> The installation links below install from this fork.

If you like this automation and would like to support its original author, you can [buy them a coffee](https://www.patreon.com/nberk/shop).

## Features

- **Spaghetti Detection:** Utilize Obico's machine learning server to identify and prevent spaghetti issues.
- **Critical/Standard Notifications:** Stay informed with customizable notifications.
- **Warn/Pause/Cancel Print on Failure Detection:** Take proactive measures by automatically warning, pausing or canceling print jobs upon the detection of spaghetti-related failures, preventing wasted material and time.
- **Third Party Camera Support:** Any camera entity can also be used for detecting failures.

## Supported Printers
| Device          | Compatibility | 
|-----------------|---------------|
| X1 Series       | ✔️          
| P1 Series       | ✔️            
| A1 Series       | ✔️             


## Prerequisites

Ensure the following prerequisites are met before installing the Spaghetti Detection Integration:

- [Bambu Lab Integration](https://github.com/greghesp/ha-bambulab) must be installed.
- A server with at least 4GB of RAM that meets the [Obico hardware requirements](https://www.obico.io/docs/server-guides/hardware-requirements/).

<br>

> **_NOTE:_** The integration does **not** support the following devices:

| Device | Compatibility | 
| ---- | ----- |
| Raspberry Pi (Any Model) | ❌
| Home Assistant Green | ❌
| Home Assistant Yellow | ❌
| Latte Panda | ❌
| Jetson Nano 2gb | ❌

## Setup

Follow these steps to set up the Spaghetti Detection Integration:

1. **Install Obico ML Server**
    - Choose between installing it as a Home Assistant Addon or as a standalone Docker container.

2. **Install `Bambu Lab P1 - Spaghetti Detection` Home Assistant Integration**
3. **Install Home Assistant Spaghetti Detection Automation Blueprint**

For detailed installation instructions and troubleshooting tips, refer to
the [Installation Guide](#link-to-installation-guide).

## 1. Install Obico ML Server

### Install Obico ML Server as Home Assistant Addon

To install Obico ML server as a Home Assistant Add-on you have 2 options:

1. Click the **Add Add-On Repository** button below, click **Add → Close** (You might need to enter the **internal
   IP address** of your Home Assistant instance first).

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https://github.com/mvso/ha-bambu-lab-p1-spaghetti-detection)

2. Add the repository URL under **Settings → Add-ons → ADD-ON STORE** and click **⋮ → Repositories**:

       https://github.com/mvso/ha-bambu-lab-p1-spaghetti-detection

After adding the repository, install the add-on. The image is built on your Home Assistant machine from the sources in
this repository, so the first installation takes several minutes.

Then open the add-on **Configuration** tab and enter a secret of your own in `obico_api_secret` before starting it. There is
no default secret, and the old value `obico_api_secret` is rejected. A good secret can be generated with
`openssl rand -hex 32`.

### Install Obico ML Server as a Standalone Docker Container

The standalone container is built from the same sources as the add-on.

1. Clone this repository and build the image:

       git clone https://github.com/mvso/ha-bambu-lab-p1-spaghetti-detection
       cd ha-bambu-lab-p1-spaghetti-detection
       docker build -t ha_bambu_lab_p1_spaghetti_detection:local addon

2. Create the container with a secret of your own (`openssl rand -hex 32` generates one):

       docker create \
         --restart unless-stopped \
         --security-opt no-new-privileges:true \
         --env ML_API_TOKEN=<your own secret> \
         --publish 3333:3333 \
         --name ha_bambu_lab_p1_spaghetti_detection \
         ha_bambu_lab_p1_spaghetti_detection:local

3. Start the container using the following command:

       docker start ha_bambu_lab_p1_spaghetti_detection

### Install Obico ML Server as a Standalone Docker Container with Docker Compose

1. Clone this repository:

       git clone https://github.com/mvso/ha-bambu-lab-p1-spaghetti-detection
       cd ha-bambu-lab-p1-spaghetti-detection

2. Build and start the container with a secret of your own:

       ML_API_TOKEN=<your own secret> docker compose up -d --build

### Security notes

- The ML server rejects every detection request until a secret of your own is configured.
- Keep port `3333` on your local network. The server fetches the image URL it is given, and the secret travels over
  plain HTTP, so it must not be reachable from the internet.
- The image URL sent to the ML server and included in notifications contains Home Assistant's short-lived camera access
  token.

## 2. Install Home Assistant Integration

### HACS

1. Click the button below to download and install the integration:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=mvso&repository=ha-bambu-lab-p1-spaghetti-detection&category=Integration)

2. Go to **Settings → Devices & services → Add Integration** and add **Bambu Lab P1 - Spaghetti Detection** integration.

### Manual

Manually copy the contents of the custom_components folder to your Home Assistant config/custom_components folder. After
restarting Home Assistant, add and configure the integration through the native integration setup.

## 3. Install Home Assistant Automation Blueprint

1. Click the button below to import the Spaghetti Detection blueprint:

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https://github.com/mvso/ha-bambu-lab-p1-spaghetti-detection/blob/main/blueprints/spaghetti_detection.yaml)

2. Go to the imported blueprint and create the automation:

![Configure the automation](docs/images/blueprint_installation.png)

### Blueprint Parameters


| Parameter | Description |
| ---- | ----- |
| **Home Assistant Host** | The address of your Home Assistant instance. Required for sending the printer camera image to the Obico ML server. Ensure to include your Home Assistant port. This address is also used for notification images. If you wish to view failure images on notifications outside your local network, provide a publicly accessible link here.
| **Obico ML API Host** | The URL of the Obico ML Server. The default port number is `3333`. If you installed the ML server via the Home Assistant Addon, the IP address should match your Home Assistant address.
| **Obico ML API Auth Token** | The authentication token for the Obico ML Server. Use the secret you configured in the addon settings or with `ML_API_TOKEN` for the docker container. There is no default value.
| **Printer Pause / Resume / Stop Button Entity** | Optional. Newer printer firmware without Developer LAN Mode does not let the Bambu Lab integration control the printer, and these buttons are then missing. Leave the fields empty to only get notified on a failure.
| **Notification Settings**   | - **Critical Notification:** Generates an audible alert even when your device is in silent mode.<br/>- **Standard Notification:** Sends a traditional notification respecting your device's audio settings.<br/>- **None:** No notifications are sent in case of a failure.
| **Notification Service**  | The notification service of your choice for selecting a single device or a group of devices, instead of alerting all mobile devices registered in home assistant. The default is `notify.notify`, which notifies all devices.


## 4. Printer Dashboard

The integration adds a dashboard called **3D printer** to the sidebar. There is nothing to configure: it finds the
entities of your Bambu Lab printer on its own, also when they have been renamed, and only shows what your printer
actually has.

- **Printer**: camera, print progress, temperatures, printer status and the spaghetti detection values.
- **Filament**: every AMS with the colour, filament, type and remaining amount of each slot, the external spool and the
  AMS climate. This view is left out when the printer has neither.

The dashboard is rebuilt each time it is opened, so a new AMS or a second printer shows up after reloading the page. It
is read-only and uses English or Norwegian labels depending on the language of Home Assistant.

The values in the spaghetti detection card are maintained by the automation, so do not change them by hand.

### Making your own editable copy

If you want to change the dashboard, or it does not appear in the sidebar:

1. Go to **Developer tools → Actions**, select **Bambu Lab P1 - Spaghetti Detection: Generate printer dashboard** and
   click **Perform action**.

2. Copy the whole response.

3. Go to **Settings → Dashboards → Add dashboard → New dashboard from scratch** and open the new dashboard.

4. Click the pencil, then **⋮ → Raw configuration editor**, replace everything with the copied response and save.

Home Assistant has no official way for an integration to add a dashboard, so the automatic one relies on internals that
can change between Home Assistant releases. If that happens the integration keeps working and logs a warning, and the
action above still gives you the dashboard.

## Credits

- **Greg Hesp ([@greghesp](https://github.com/greghesp))**: https://github.com/greghesp/ha-bambulab
- **Obico ([@TheSpaghettiDetective](https://github.com/TheSpaghettiDetective))**: https://github.com/TheSpaghettiDetective/obico-server
