import kwutil
import fsspec
import ubelt as ub


class SSHAPI:
    """
    Interact with home assistant via the ssh filesystem

    Requires:
        pip install fsspec[ssh] sshfs
    """

    def __init__(self, ssh_hostname):
        self.ssh_hostname = ssh_hostname
        fs_cls = fsspec.get_filesystem_class('ssh')
        fs = fs_cls(host=ssh_hostname)
        self.fs = fs

    def read_automations(self):
        automation_text = self.fs.read_text('./homeassistant/automations.yaml')
        automations = kwutil.Yaml.coerce(automation_text)
        self.orig_automation_text = automation_text
        self.orig_automations = kwutil.Yaml.coerce(automation_text)
        self.automations = kwutil.Yaml.coerce(automation_text)

        if 0:
            for automation in automations:
                print(kwutil.Yaml.dumps(automation, version='1.1'))

    def read_dashboards(self):
        """
        Can grab these from via ssh, maybe a better way to do it.
        But on disk they are in /root/homeassistant/.storage/lovelace*
        """
        storage_paths = self.fs.ls('./homeassistant/.storage')

        dashboard_configs = []
        for fpath in storage_paths:
            if 'lovelace' in ub.Path(fpath).name:
                dashboard_configs.append(fpath)

        fpath_to_text = {}
        for fpath in dashboard_configs:
            # Open and read the file
            fpath_to_text[fpath] = self.fs.read_text(fpath)

        self.orig_dashboard_text = fpath_to_text
        self.dashboards = {fpath: kwutil.Yaml.coerce(text) for fpath, text in fpath_to_text.items()}
        # print(f'fpath_to_data = {ub.urepr(fpath_to_data, nl=-1)}')

    def write_dashboard(self, dry=False):
        for fpath, content in self.dashboards.items():
            old_text = self.orig_dashboard_text[fpath]
            old_text = kwutil.Json.dumps(kwutil.Json.loads(old_text), indent='  ')
            new_text = kwutil.Json.dumps(content, indent='  ')
            if new_text != old_text:
                print('diff', fpath)
                import xdev as xd
                print(xd.difftext(old_text, new_text, context_lines=3, colored=True))
                if not dry:
                    print('Writing')
                    self.fs.write_text(fpath, new_text)
                else:
                    print('Not Writing. Dry Run.')
            else:
                print('same', fpath)

    def write_automations(self, dry=False):
        old_text = kwutil.Yaml.dumps(kwutil.Yaml.loads(self.orig_automation_text, version='1.1'), version='1.1')
        new_text = kwutil.Yaml.dumps(self.automations, version='1.1')
        if new_text != old_text:
            import xdev as xd
            print(xd.difftext(old_text, new_text, context_lines=3, colored=True))
            if not dry:
                print('Writing')
                self.fs.write_text('./homeassistant/automations.yaml', new_text)
            else:
                print('Not Writing. Dry Run.')
