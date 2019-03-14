%global debug_package %{nil}
%global __provides_exclude (npm)
%global __requires_exclude (npm|nodejs.abi)

%global arch       %(test $(rpm -E%?_arch) = x86_64 && echo "x64" || echo "ia32")
%global strip()    find %1 -name "*.node" -exec strip {} \\;
%global yarn       node --max-old-space-size=%{mem_limit} %{_bindir}/npx yarn
%global mem_limit  4095

%global nodesqlurl https://github.com/mapbox/node-sqlite3
%global nodesqltgz %{nodesqlurl}/archive/%{nodesqlver}/%{nodesqlver}.tar.gz
%global nodesqlver 5bb0dc0e7511cf42cfda72f02e1354c4962c192b

%global commit     a684fe7ee136f89d92fa25ee0b8f9bdeacd104b6
%global scommit    %(c=%{commit}; echo ${c:0:7})
%global target     3.0.10

Name:    vscode
Version: 1.30.0
Release: 2%{?dist}
Summary: Visual Studio Code - An open source code editor
License: MIT
URL:     https://github.com/Microsoft/vscode
Source0: %{url}/archive/%{scommit}/%{name}-%{scommit}.tar.gz
Source1: product-release.json

BuildRequires: openssl
BuildRequires: python2, git
BuildRequires: npm, node-gyp
BuildRequires: pkgconfig(x11)
BuildRequires: pkgconfig(xkbfile)
BuildRequires: pkgconfig(libsecret-1)
BuildRequires: desktop-file-utils
BuildRequires: libappstream-glib
# sysctl_apply macro
BuildRequires: systemd
# /usr/lib/systemd/systemd-sysctl
Requires:      systemd
Requires:      electron >= %{target}

%description
 VS Code is a new type of tool that combines the simplicity of a code editor
 with what developers need for their core edit-build-debug cycle. Code provides
 comprehensive editing and debugging support, an extensibility model, and
 lightweight integration with existing tools.

%prep
%setup -q -n %{name}-%{commit}

# Skip preinstall check
sed -i '/preinstall/d' package.json

# Use system python2
# https://github.com/mapbox/node-sqlite3/issues/1044
sed -i '/sqlite/s|:.*"|: "%{nodesqltgz}"|' package.json

# Skip smoke test
sed -i '/smoketest/d' build/npm/postinstall.js

# Do not download electron
sed -i '/pipe.electron/d' build/gulpfile.vscode.js

# Set output directory
sed -i "/destin/s|=.*|='%{name}';|; /destin/s|result|all|
        /Asar/s|app|%{name}|" build/gulpfile.vscode.js

# Build native modules for system electron
sed -i '/target/s|".*"|"%{target}"|' .yarnrc

# Patch appdata and desktop file
sed -i resources/linux/code.{appdata.xml,desktop} \
 -e 's|%{_datadir}.*@@|%{name}|
     s|@@NAME_SHORT@@|VSCode|
     s|@@NAME_LONG@@|Visual Studio Code|
     s|@@NAME@@|%{name}|
     s|@@ICON@@|%{name}|
     s|@@LICENSE@@|MIT|
     s|inode/directory;||'

# Output release product.json
cp %{SOURCE1} product.json

# Disable crash reporter and telemetry service by default
sed -i '/default/s|:.*,|:false,|' src/vs/platform/telemetry/common/telemetryService.ts \
    src/vs/workbench/services/crashReporter/electron-browser/crashReporterService.ts

%build
export BUILD_SOURCEVERSION="%{commit}"
export NODE_OPTIONS="--max-old-space-size=%{mem_limit}"
npm config set python="/usr/bin/python2"
%yarn install
%strip node_modules
%yarn gulp %{name}-linux-%{arch}-min
rm -rf %{name}/*min

# Set application name
sed -i '/Code/s|:.*"|: "Code"|' %{name}/package.json

%install
# Install data files
install -d %{buildroot}%{_libdir}
cp -r %{name} %{buildroot}%{_libdir}

# Install binary
install -d %{buildroot}%{_bindir}
cat <<EOT > %{buildroot}%{_bindir}/%{name}
#!/usr/bin/env bash
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root
# for license information.

VSCODE_PATH="%{_libdir}/%{name}"
ELECTRON="%{_bindir}/electron"
CLI="\$VSCODE_PATH/out/cli.js"
ELECTRON_RUN_AS_NODE=1 "\$ELECTRON" "\$CLI" --app="\$VSCODE_PATH" "\$@"
exit \$?
EOT

# Install appdata and desktop file
pushd resources/linux
install -Dm644 code.appdata.xml %{buildroot}%{_datadir}/metainfo/%{name}.appdata.xml
install -Dm644 code.desktop     %{buildroot}%{_datadir}/applications/%{name}.desktop
install -Dm644 code.png         %{buildroot}%{_datadir}/pixmaps/%{name}.png

# Set user watch files
install -d %{buildroot}%{_sysconfdir}/sysctl.d
cat > %{buildroot}%{_sysconfdir}/sysctl.d/50-%{name}.conf <<EOF
fs.inotify.max_user_watches=$((8192*64))
EOF

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/%{name}.desktop
appstream-util validate-relax --nonet %{buildroot}%{_datadir}/metainfo/%{name}.appdata.xml
%yarn monaco-compile-check
%yarn strict-null-check

%posttrans
%sysctl_apply %{_sysconfdir}/sysctl.d/50-%{name}.conf

%files
%doc README.md ThirdPartyNotices.txt
%license LICENSE.txt
%{_sysconfdir}/sysctl.d/50-%{name}.conf
%attr(755,-,-) %{_bindir}/%{name}
%{_libdir}/%{name}/
%{_datadir}/pixmaps/%{name}.png
%{_datadir}/applications/%{name}.desktop
%{_datadir}/metainfo/%{name}.appdata.xml

%changelog
* Fri Dec 14 2018 - 1.30.0-2
- Fix save file for electron-3
- Disable crash reporter and telemetry service by default
- Set max memory size via NODE_OPTIONS
