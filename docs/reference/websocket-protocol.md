# WebSocket Protocol

WebSocket ingestion protocol used between the Foundry userscript client and Foundry Bridge server.

## Endpoint

|Item|Value|
|---|---|
|URL|`ws://<bridge-host>:8765`|
|Transport|WebSocket|
|Binary payload|PCM16 audio frame bytes|

## Session behavior

|Behavior|Description|
|---|---|
|Connection timeout|Idle connections are closed after 30 seconds of no activity|
|Identification gate|`game_identify` must be sent before participant/audio events are accepted|
|Audio framing|Each audio binary frame is paired with the most recent `type=audio` JSON header|

## Client-to-server JSON messages

### `game_identify`

Registers the campaign namespace for the connection.

|Field|Type|Required|
|---|---|---|
|`type`|string|yes (`game_identify`)|
|`hostname`|string|yes|
|`world_id`|string|yes|
|`name`|string|no|

### `participant_attached`

Declares a participant stream.

|Field|Type|Required|
|---|---|---|
|`type`|string|yes (`participant_attached`)|
|`participantId`|string|yes|
|`name` or `label`|string|yes|

### `audio` (header)

Header metadata for the subsequent binary audio frame.

|Field|Type|Required|
|---|---|---|
|`type`|string|yes (`audio`)|
|`participantId`|string|yes|
|`name` / `label`|string|recommended|
|`characterName`|string|optional|
|`sampleRate`|integer|recommended|
|`channels`|integer|recommended|
|`samples`|integer|optional|
|`ts`|integer|optional|

## Client-to-server binary message

Raw audio bytes (PCM16) corresponding to the last `audio` JSON header.

## Server-to-client JSON messages

### `game_identify_ack`

|Field|Type|
|---|---|
|`type`|`game_identify_ack`|
|`game_id`|integer|

### `game_identify_nack`

|Field|Type|
|---|---|
|`type`|`game_identify_nack`|
|`reason`|string|

### `error`

|Field|Type|
|---|---|
|`type`|`error`|
|`message`|string|

## Validation rules

|Rule|Result|
|---|---|
|Non-`game_identify` message before game identification|message dropped, `error` response|
|`participant_attached` without `participantId` or `name/label`|message dropped, `error` response|
|Binary frame without prior `audio` header|frame dropped|
|Malformed JSON message|message ignored, `error` response|

## See also

- [How to integrate Foundry VTT userscript](../how-to/foundry-integration.md)
- [How to troubleshoot common issues](../how-to/troubleshoot-common-issues.md)
- [Architecture and design decisions](../architecture.md)
