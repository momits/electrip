%define name Electrip
%define version 5.0.8
%define release 1

Summary: Model railroad control using Gamepads
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.gz
License: GPL Version 3
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Moritz Renftle momits@users.sourceforge.net
Url: http://www.electrip.sourceforge.net

Requires: "python(abi) = 2.7"
Requires: "gtk3 >= 3.10.2"
Requires: "pygame >= 1.9.1"

BuildRequires: desktop-file-utils

%description
Electrip is a SRCP-Client which allows you to control your locos
with Gamepads. Electrip is very configurable and offers some powerful
features, including the simulation of loco sounds.

%prep
%setup -n %{name}-%{version}

%build
%{__python} setup.py build

%install
%{__python} setup.py install -O1 --root=%{buildroot} --skip-build --record=INSTALLED_FILES
sed 's/@pythondir@/%{python_sitelib}/g' electrip.in > %{_bindir}/electrip
desktop-file-install --dir %{buildroot}%{_datadir}/applications electrip.desktop


%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES
%defattr(-,root,root)

%post
/bin/touch --no-create %{_datadir}/icons/hicolor &>/dev/null || :

%postun
if [ $1 -eq 0 ] ; then
    /bin/touch --no-create %{_datadir}/icons/hicolor &>/dev/null
    /usr/bin/gtk-update-icon-cache %{_datadir}/icons/hicolor &>/dev/null || :
fi

%posttrans
/usr/bin/gtk-update-icon-cache %{_datadir}/icons/hicolor &>/dev/null || :

