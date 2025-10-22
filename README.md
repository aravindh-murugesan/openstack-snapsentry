# openstack-snapsentry
Automated Snapshot Management for Openstack Volumes.

SnapSentry extends OpenStack’s snapshot capabilities by introducing a lightweight, metadata-driven approach to automated volume snapshots. This is intended for simpler solution, you should you a proper backup tool if you need application consistency.

While Cinder natively supports creating, deleting, and restoring volume snapshots, it lacks built-in scheduling. SnapSentry fills that gap by using volume and snapshot properties to define snapshot behavior — including frequency, retention, and start time — without introducing any additional scheduling complexity inside the service itself.

Instead of bundling a scheduler, SnapSentry is designed to work seamlessly with external automation systems such as Argo Workflows, Apache Airflow, or even simple cron jobs on Unix-like systems. This makes it easy to integrate into existing CI/CD or cloud-management pipelines while keeping the core design simple, modular, and OpenStack-native.

Snapsentry supports a few different policy types for a volumes,
1. Daily Snapshot at a set time
2. Weekly Snapshot at a set day and time.
3. Monthly Snapshot at a set date and time.

## Configurations

### Global - Application Configuration

The application can be configured either via environment variables or a config.yaml file.

| Parameter    | Description                         | Required | Choices                      | Default      | Enviornment Value       |
| ------------ | ----------------------------------- | -------- | ---------------------------- | ------------ | ----------------------- |
| organization | Organization Name for whitelabeling | NO       | `-`                          | `snapsentry` | SNAPSENTRY_ORGANIZATION |
| log_level    | Controls the logging of the program | NO       | `INFO`<br>`DEBUG`<br>`ERROR` | `INFO`       | SNAPSENTRY_LOG_LEVEL    |


### Volume Metadata

| Parameter                              | Description                                              | Required | Choices |
| -------------------------------------- | -------------------------------------------------------- | -------- | ------- |
| x-*${organization}*-snapsentry-managed | Indicates if this volume has to be managed by SnapSentry |          | `true`  |

#### Daily Snapshots

| Parameter                                | Description                                                     | Required | Choices                                                                        | Default |
| ---------------------------------------- | --------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------ | ------- |
| x-*${organization}*-daily-enabled        | Indicates if daily snapshot workflow is expected for the volume | `NO`     | `true`<br>`false`                                                              | `false` |
| x-*${organization}*-daily-start-time     | Time for the snapshot to trigger.                               | `NO`     | `HH:MM`                                                                        | 23:29   |  |
| x-*${organization}*-daily-timezone       | Indicates the timezone for the snapshot schedule                | `NO`     | [TZ Identifiers](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) | `UTC`   |
| x-*${organization}*-daily-retention-type | Indicates how the expiry has to be handled                      | `NO`     | `time`                                                                         | `time`  |
| x-*${organization}*-daily-retention-days | Indicates how long the snapshot has to be stored.               | `NO`     |                                                                                | 7       |

#### Weekly Snapshots

| Parameter                                 | Description                                                      | Required | Choices                                                                                  | Default  |
| ----------------------------------------- | ---------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------- | -------- |
| x-*${organization}*-weekly-enabled        | Indicates if weekly snapshot workflow is expected for the volume | `NO`     | `true`<br>`false`                                                                        | `false`  |
| x-*${organization}*-weekly-start-time     | Time for the snapshot to trigger.                                | `NO`     | `HH:MM`                                                                                  | 23:29    |
| x-*${organization}*-weekly-start-day      | Indicates the day of the week for the snapshot                   | `NO`     | `monday`<br>`tuesday`<br>`wednesday`<br>`thrusday`<br>`friday`<br>`saturday`<br>`sunday` | `sunday` |
| x-*${organization}*-weekly-timezone       | Indicates the timezone for the snapshot schedule                 | `NO`     | [TZ Identifiers](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)           | `UTC`    |
| x-*${organization}*-weekly-retention-type | Indicates how the expiry has to be handled                       | `NO`     | `time`                                                                                   | `time`   |
| x-*${organization}*-weekly-retention-days | Indicates how long the snapshot has to be stored.                | `NO`     |                                                                                          | 30       |

#### Monthly Snapshots

| Parameter                                  | Description                                                       | Required | Choices                                                                        | Default |
| ------------------------------------------ | ----------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------ | ------- |
| x-*${organization}*-monthly-enabled        | Indicates if monthly snapshot workflow is expected for the volume | `NO`     | `true`<br>`false`                                                              | `false` |
| x-*${organization}*-monthly-start-time     | Time for the snapshot to trigger.                                 | `NO`     | `HH:MM`                                                                        | 23:29   |  |
| x-*${organization}*-monthly-start-date     | Indicates the day of the week for the snapshot                    | `NO`     | `1`-`31`                                                                       | 1       |
| x-*${organization}*-monthly-timezone       | Indicates the timezone for the snapshot schedule                  | `NO`     | [TZ Identifiers](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) | `UTC`   |
| x-*${organization}*-monthly-retention-type | Indicates how the expiry has to be handled                        | `NO`     | `time`                                                                         | `time`  |
| x-*${organization}*-monthly-retention-days | Indicates how long the snapshot has to be stored.                 | `NO`     |                                                                                | 90      |

