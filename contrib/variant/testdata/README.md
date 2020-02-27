These instructions show how to test the operation of finding the coreboot
CL when:
* the CL hasn't been pushed to review.coreboot.org yet
* the CL has been pushed, but has not been upstreamed into the chromiumos tree yet
* the CL has been upstreamed into chromiumos

The test yaml files include the CLs for the creation of the Kindred variant.
The coreboot CL for Kindred is coreboot:32936, and was upstreamed as
chromium:1641906. These CLs have long since merged, and so nothing will be
uploaded to any gerrit instances or merged into ToT.

`need_to_push.yaml` has the change\_id for the coreboot CL modified so that
the CL cannot be found, which makes it look like the CL has not been pushed.
The program will ask the user to push it to coreboot.

`need_to_upstream.yaml` also has the change\_id for the coreboot CL modified,
but the gerrit instance (coreboot) and CL number (32936) are already there,
so the CL has already been found. However, searching chromium for that
change\_id as an original-change-id will fail, indicating that the CL has
not been upstreamed from coreboot yet.

`upstreamed.yaml` has the correct change\_id for the coreboot CL. The program
will find the CL in coreboot, then find the upstreamed CL in chromium, and
proceed to the cq\_depend step (which is not yet implemented).

```
(cr) $ cp testdata/need_to_push.yaml ~/.new_variant.yaml
(cr) $ ./new_variant.py --continue
INFO:root:Running step push_coreboot
INFO:requests.packages.urllib3.connectionpool:Starting new HTTPS connection (1): review.coreboot.org
ERROR:root:The following commit needs to be pushed to coreboot.org:
ERROR:root:  Branch "kindred"
ERROR:root:  in directory "/mnt/host/source/src/third_party/coreboot"
ERROR:root:  with change-id "Ithischangeidwillnotbefoundbecauseitdoesntexist"
ERROR:root:Please push the branch to review.coreboot.org, and then re-start this program with --continue
(cr) $ cp testdata/need_to_upstream.yaml ~/.new_variant.yaml
(cr) $ ./new_variant.py --continue
INFO:root:Running step push_coreboot
INFO:root:Running step upload_CLs
INFO:root:Running step find_coreboot_upstream
ERROR:root:Program cannot continue until coreboot CL is upstreamed.
ERROR:root:(coreboot:32936, change-id Ichangeiddoesntmatterbecausewealreadyknowtheclnumber)
ERROR:root:Please wait for the CL to be upstreamed, then run this program again with --continue
(cr) $ cp testdata/upstreamed.yaml ~/.new_variant.yaml
(cr) $ ./new_variant.py --continue
INFO:root:Running step push_coreboot
INFO:root:Running step upload_CLs
INFO:root:Running step find_coreboot_upstream
INFO:root:Running step clean_up
```
