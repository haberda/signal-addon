# Signal Messenger add-on for Home Assistant

This add-on allows you to send messages via Signal Messenger to recipients who have the Signal Messenger application installed on their devices.

## Installation

- Add this repository to the Home Assistant Supervisor Add-on Store
- Click install
- Choose your desired port
- Choose your desired options
- Click Start

## Use

Instructions for use can be found in the official [docs](https://www.home-assistant.io/integrations/signal_messenger/).

## Security

This add-on exposes the upstream Signal REST API on its configured port. The API does not provide authentication, so any client that can reach that port can use the linked Signal account, including sending and receiving messages. Run the add-on only on a trusted network, do not expose or port-forward its REST API port to the internet, and use a firewall, VPN, or authenticated reverse proxy if remote access is required.

## Options

### Mode

This option allows you to set the MODE environment variable. This replaces the Use Native variable and adds an additional mode.

Valid options:

- 'normal': Every REST API request invokes the signal-cli JAVA application (slowest mode)
- 'native': Every REST API request invokes a compiled native image (faster than the normal mode)
- 'json-rpc': The signal-cli JAVA application is started once and the REST API wrapper communicates via JSON-RPC with it (slow startup time, but once the Java application is running, it should be the fastest)
- 'json-rpc-native': The signal-cli native application is started once and the REST API wrapper communicates via JSON-RPC (fastest mode with lower memory usage)

### Auto receive

This option is recommened by the up-stream project to be enabled if you do not have a rest api endpoint setup to listen for new messages. See documentation [here](https://github.com/bbernhard/signal-cli-rest-api#auto-receive-schedule) for more details. This option does not apply to `json-rpc` or `json-rpc-native` mode and will be ignored in those modes.

Valid options:

- `off`: Disable Auto receive
- `on`: Enable Auto receive (default)

### Default Signal Text Mode

Sets the default text mode for outbound messages. Only comes into play, if `text_mode` is not set for an individual message as part of the request payload.

- `normal`: no formatting options
- `styled`: renders `*italic*`, `**bold**`, `~strikethrough~`

### Log Level

Controls the upstream REST API log verbosity.

- `debug`: detailed diagnostic logging
- `info`: routine operational logging (default)
- `warn`: warnings and errors only
- `error`: errors only

### JSON-RPC Settings

These options apply only to `json-rpc` and `json-rpc-native` modes.

#### Trust New Identities

Controls how Signal identity keys are trusted when they are first encountered.

- `on-first-use`: trust the first identity seen for a recipient (default)
- `always`: automatically trust new or changed identities
- `never`: do not automatically trust identities

#### Ignore Downloaded Media

When enabled, the associated media type is not automatically downloaded when receiving messages. All options default to `false`.

- Ignore attachments
- Ignore stories
- Ignore avatars
- Ignore stickers

### SIGNAL-CLI Command Timeout

This option sets the time in seconds to wait before timing out the signal cli command. This option does not apply to `json-rpc` or `json-rpc-native` mode and will be ignored in those modes. (default: 60s)

## Versioning

This add-on follows the versioning of the upstream container. There is very little difference between this add-on and the container found [here](https://github.com/bbernhard/signal-cli-rest-api).
As of this writing the upstream container versioning uses the 0.xx pattern for releases. This add-on follows the same pattern, but uses 0.xx.y where y indicates a change from the upstream that is related to Home Assistant add-on specific changes.

## Differences with the Upstream

The primary difference between this add-on and the upstream is the location of persistent storage. Signal CLI data is stored in `/config` through the `SIGNAL_CLI_CONFIG_DIR` environment variable, rather than upstream's default `/home/.local/share/signal-cli`. The add-on reads its Home Assistant configuration options separately from `/data/options.json`.
There is also a script that runs to allow for setting the above option(s).

## Bug Reporting

Bug reports can be filed either with the [add-on repository](https://github.com/haberda/hassio_addons), or with the [upstream repository](https://github.com/bbernhard/signal-cli-rest-api).
Please attempt to determine if your bug is related to add-on specific issues, or application issues before filing your report. Add-on specific issues should be submitted to the add-on repository, application specific issues should be filed with the upstream repository.
