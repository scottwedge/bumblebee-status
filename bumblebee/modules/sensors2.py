# -*- coding: UTF-8 -*-

"""Displays sensor temperature and CPU frequency

Parameters:

    * sensors2.chip: "sensors -u" compatible filter for chip to display (default to empty - show all chips)
    * sensors2.showcpu: Enable or disable CPU frequency display (default: true)
    * sensors2.showtemp: Enable or disable temperature display (default: true)
    * sensors2.showfan: Enable or disable fan display (default: true)
    * sensors2.showother: Enable or display "other" sensor readings (default: false)
    * sensors2.showname: Enable or disable show of sensor name (default: false)
    * sensors2.chip_include: Comma-separated list of chip to include (defaults to "" will include all by default, example: "coretemp,bat")
    * sensors2.chip_exlude:Comma separated list of chip to exclude (defaults to "" will include none by default)
    * sensors2.field_include: Comma separated list of chip to include (defaults to "" will include all by default, example: "temp,fan")
    * sensors2.field_exlude: Comma separated list of chip to exclude (defaults to "" will exclude none by default)
    * sensors2.chip_field_exclude: Comma separated list of chip field to exclude (defaults to "" will exclude none by default, example: "coretemp-isa-0000.temp1,coretemp-isa-0000.fan1")
    * sensors2.chip_field_include: Comma-separated list of adaper field to include (defaults to "" will include all by default)
"""

import re

import bumblebee.util
import bumblebee.output
import bumblebee.engine

class Module(bumblebee.engine.Module):
    def __init__(self, engine, config):
        super(Module, self).__init__(engine, config, None)
        self._chip = self.parameter("chip", "")
        self._data = {}
        self._update()

        self.widgets(self._create_widgets())

    def update(self, widgets):
        self._update()
        for widget in widgets:
            self._update_widget(widget)

    def state(self, widget):
        widget_type = widget.get("type", "")
        try:
            data = self._data[widget.get("adapter")][widget.get("package")][widget.get("field")]
            if "crit" in data and float(data["input"]) > float(data["crit"]):
                return ["critical", widget_type]
            if "max" in data and float(data["input"]) > float(data["max"]):
                return ["warning", widget_type]
        except:
            pass
        return [widget_type]

    def _create_widgets(self):
        widgets = []
        show_temp = bumblebee.util.asbool(self.parameter("showtemp", "true"))
        show_fan = bumblebee.util.asbool(self.parameter("showfan", "true"))
        show_other = bumblebee.util.asbool(self.parameter("showother", "false"))
        include_chip = tuple(filter(len, self.parameter("chip_include", "").split(",")))
        exclude_chip = tuple(filter(len, self.parameter("chip_exclude", "").split(",")))
        include_field = tuple(filter(len, self.parameter("field_include", "").split(",")))
        exclude_field = tuple(filter(len, self.parameter("field_exclude", "").split(",")))
        include_chip_field = tuple(filter(len, self.parameter("chip_field_include", "").split(",")))
        exclude_chip_field = tuple(filter(len, self.parameter("chip_field_exclude", "").split(",")))

        if bumblebee.util.asbool(self.parameter("showcpu", "true")):
            widget = bumblebee.output.Widget(full_text=self._cpu)
            widget.set("type", "cpu")
            widgets.append(widget)

        for adapter in self._data:
            if include_chip or exclude_chip:
                if include_chip:
                    if any([chip not in adapter for chip in include_chip]):
                        continue
                else:
                    if any([chip in adapter for chip in exclude_chip]):
                        continue

            if include_chip_field:
                try:
                    if any([i.split('.')[0] not in adapter for i in include_chip_field]):
                        continue
                except:
                    pass

            for package in self._data[adapter]:
                if bumblebee.util.asbool(self.parameter("showname", "false")):
                    widget = bumblebee.output.Widget(full_text=package)
                    widget.set("data", self._data[adapter][package])
                    widget.set("package", package)
                    widget.set("field", "")
                    widget.set("adapter", adapter)
                    widgets.append(widget)
                for field in self._data[adapter][package]:

                    if include_field or exclude_field:
                        if include_field:
                            if any([included not in field for included in include_field]):
                                continue
                        else:
                            if any([excluded in field for excluded in exclude_field]):
                                continue

                    try:
                        if include_chip_field or exclude_chip_field:
                            if include_chip_field:
                                if any([i.split('.')[1] not in field for i in include_chip_field if i.split('.')[0] in adapter]):
                                    continue
                            else:
                                if any([i.split('.')[1] in field for i in exclude_chip_field if i.split('.')[0] in adapter]):
                                    continue
                    except:
                        pass

                    widget = bumblebee.output.Widget()
                    widget.set("package", package)
                    widget.set("field", field)
                    widget.set("adapter", adapter)
                    if "temp" in field and show_temp:
                        # seems to be a temperature
                        widget.set("type", "temp")
                        widgets.append(widget)
                    if "fan" in field and show_fan:
                        # seems to be a fan
                        widget.set("type", "fan")
                        widgets.append(widget)
                    elif show_other:
                        # everything else
                        widget.set("type", "other")
                        widgets.append(widget)
        return widgets

    def _update_widget(self, widget):
        if widget.get("field", "") == "":
            return # nothing to do
        data = self._data[widget.get("adapter")][widget.get("package")][widget.get("field")]
        if "temp" in widget.get("field"):
            widget.full_text(u"{:0.01f}°C".format(data["input"]))
        elif "fan" in widget.get("field"):
            widget.full_text(u"{:0.0f}RPM".format(data["input"]))
        else:
            widget.full_text(u"{:0.0f}".format(data["input"]))

    def _update(self):
        output = bumblebee.util.execute("sensors -u {}".format(self._chip))
        self._data = self._parse(output)

    def _parse(self, data):
        output = {}
        package = ""
        adapter = None
        chip = None
        for line in data.split("\n"):
            if "Adapter" in line:
                # new adapter
                line = line.replace("Adapter: ", "")
                output[chip + " " + line] = {}
                adapter = chip + " " + line
            chip = line #default - line before adapter is always the chip
            if not adapter: continue
            key, value = (line.split(":") + ["", ""])[:2]
            if not line.startswith(" "):
                # assume this starts a new package
                if package in output[adapter] and output[adapter][package] == {}:
                    del output[adapter][package]
                output[adapter][key] = {}
                package = key
            else:
                # feature for this chip
                try:
                    name, variant = (key.strip().split("_", 1) + ["",""])[:2]
                    if not name in output[adapter][package]:
                        output[adapter][package][name] = { }
                    if variant:
                        output[adapter][package][name][variant] = {}
                    output[adapter][package][name][variant] = float(value)
                except Exception as e:
                    pass
        return output

    def _cpu(self, _):
        mhz = None
        try:
            output = open("/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq").read()
            mhz = int(float(output)/1000.0)
        except:
            output = open("/proc/cpuinfo").read()
            m = re.search(r"cpu MHz\s+:\s+(\d+)", output)
            if m:
                mhz = int(m.group(1))
            else:
                m = re.search(r"BogoMIPS\s+:\s+(\d+)", output)
                if m:
                    return "{} BogoMIPS".format(int(m.group(1)))
        if not mhz:
            return "n/a"

        if mhz < 1000:
            return "{} MHz".format(mhz)
        else:
            return "{:0.01f} GHz".format(float(mhz)/1000.0)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
