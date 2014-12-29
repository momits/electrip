%define name electrip
%define version 5.3.9
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
Url: http://www.electrip.sourceforge.net

Requires: python(abi) = 2.7
Requires: gtk3 >= 3.10.2
Requires: pygame >= 1.9.1

BuildRequires: desktop-file-utils
BuildRequires: xdg-utils

%description
Electrip is a SRCP-Client which allows you to control your locos
with Gamepads. Electrip is very configurable and offers some powerful
features, including the simulation of loco sounds.

%prep
%autosetup -n %{name}-%{version}

%build
%{__python} setup.py build

%install
%{__python} setup.py install -O1 --root=%{buildroot} --skip-build --record=INSTALLED_FILES
mkdir %{buildroot}%{_bindir}
sed 's/@pythondir@/'$( echo %{python_sitelib} | sed 's|/|\\/|g' | sed 's| |\\ |g' )/g electrip.in > %{buildroot}%{_bindir}/electrip
mkdir -p  %{buildroot}%{_datadir}/icons/hicolor/128x128/apps && cp electrip/icons/logo_icon_128.png "$_"/electrip.png
mkdir -p  %{buildroot}%{_datadir}/icons/hicolor/64x64/apps && cp electrip/icons/logo_icon_64.png "$_"/electrip.png
desktop-file-install --dir %{buildroot}%{_datadir}/applications electrip.desktop

%clean
rm -rf %{buildroot}

%files -f INSTALLED_FILES
%defattr(0644,root,root)
%attr(0755,root,root) %{_bindir}/electrip
%{_datadir}/applications/electrip.desktop
%{_datadir}/icons/hicolor/128x128/apps/electrip.png
%{_datadir}/icons/hicolor/64x64/apps/electrip.png

%post
/bin/touch --no-create %{_datadir}/icons/hicolor &>/dev/null || :

%postun
if [ $1 -eq 0 ] ; then
    /bin/touch --no-create %{_datadir}/icons/hicolor &>/dev/null
    /usr/bin/gtk-update-icon-cache %{_datadir}/icons/hicolor &>/dev/null || :
fi

%posttrans
/usr/bin/gtk-update-icon-cache %{_datadir}/icons/hicolor &>/dev/null || :

