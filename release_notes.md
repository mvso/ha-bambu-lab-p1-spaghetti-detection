### V1.4.0

- The power plug card and the picture behind the dashboard overview now come from the blueprint's new optional inputs
  Printer Power Switch and Second Camera Entity, instead of fixed entities in the code.
- The blueprint has an optional second camera. Both cameras are analysed and the highest detection score counts. If one
  camera fails the other one is still used, and the notification shows the picture of the camera with the highest score.
- Tests that run the blueprint's detection steps against fake services.

### V1.3.0

- The printer view of the dashboard is now laid out in sections from left to right, with an overview picture of the
  camera and the key values of the printer first.
- Optional cards for a power plug and an external camera, shown only when those entities exist.

### V1.2.0

- The integration adds a printer dashboard to the sidebar, with the camera, print progress, temperatures, AMS and
  filament. The entities of your printer are found automatically.
- New `generate_dashboard` action that returns the same dashboard for pasting into a dashboard of your own.

### V1.1.1

> ### Breaking Change
> The ML server no longer has a default secret and rejects the old value `obico_api_secret`. Set a secret of your own
> in the addon configuration (or `ML_API_TOKEN` for docker) and enter the same value in the automation.

- The configured secret is now actually enforced by the addon.
- The addon and the standalone container are built from this repository instead of prebuilt images, with pinned
  Darknet sources and checksum-verified model weights.
- Updated Python dependencies, and the server no longer runs as root.
- The server only fetches `http`/`https` images of at most 20 MB.

### V1.1.0

> ### Breaking Change
> Image entity of ha-bambulab no longer works due to a change in official Bambu Lab APIs. Make sure to update [ha-bambulab](https://github.com/greghesp/ha-bambulab) integration to v2.0.23 or higher version.

- Spaghetti Detection automation is now compatible with all Bambu Lab printers supported by ha-bambulab integration!
  - X1 Series
  - P1 Series
  - A1 Series
- Third party cameras can also be used for detecting failures now!

### V1.0.0
- Initial release