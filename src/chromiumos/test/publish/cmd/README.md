# cros-pubilsh

cros-publish provides various publish services for ChromiumOS. All of the services supports both CLI and server modes. Currently there are 3 pubish services:
1. gcs-publish
2. tko-publish
3. rdb-publish

## Design doc
go/cros-publish-dd

## Testing services

### gcs-pubilsh (CLI)
All provided paths should absolute paths.
```shell
publish/cmd/gcs-publish$ go build .
publish/cmd/gcs-publish$ ./gcs-publish cli -input <input_file_path> -output <desired_output_file_path> -log-path <desired_log_path>
```
Examples:
1. input_file_path = /usr/local/google/home/<...>/publish/cmd/gcs-publish/input.json
2. desired_output_file_path = /usr/local/google/home/<...>/publish/cmd/gcs-publish/output.json
3. desired_log_path = /usr/local/google/home/<...>/publish/cmd/gcs-publish/logs

### gcs-pubilsh (Server)

Start gcs-publish server
```shell
publish/cmd/gcs-publish$ go build .
publish/cmd/gcs-publish$ ./gcs-publish server --port <port_number>
server_command.go: running server mode:
gcs_publish_server.go: gcs-publish-service listen to request at  [::]:44349
```
Examples:
port_number = 44349 (Provide 0 if we want to start the server on a random available port)

Once the server has started, you may use [`grpc_cli`](http://go/grpc_cli) to
interact with the services. Example:
```shell
$ grpc_cli ls localhost:44349 chromiumos.test.api.GenericPublishService --channel_creds_type insecure
Publish
Publish
```
Create `key.json` file in the same folder(gcs-publish) where the binary lives. This file should have the GCS credentials that will be used for GCS upload. This info will be made part of the input soon and will be expected to provide this as part of input.
```shell
$ grpc_cli call localhost:38869 chromiumos.test.api.GenericPublishService.Publish --infile=input.textproto --channel_creds_type insecure
connecting to localhost:44349
name: "operations/655953d1-968f-4e61-96c8-8929c53c002a"
done: true
response {
  type_url: "type.googleapis.com/chromiumos.test.api.PublishResponse"
}
Rpc succeeded with OK status
```
Examples:
1. input.textproto = http://go/paste/6585018561331200 (Please modify the aritifact_dir_path.path and gcs_path.path correctly)
