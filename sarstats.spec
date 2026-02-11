Name:           sarstats
Version:        0.7
Release:        1%{?dist}
Summary:        Creates a performance report from sar files
License:        GPLv2
URL:            https://github.com/mbaldessari/sarstats
Source0:        sarstats-%{version}.tar.gz
BuildArch:	noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
Requires:       python3-matplotlib
Requires:	python3-reportlab
Requires:	python3-numpy
Requires:	python3-dateutil

%description
Generate a PDF report of one or more sar files

%prep
%setup -q


%build
%{__python3} setup.py build

%install
rm -rf $RPM_BUILD_ROOT
%{__python3} setup.py install --skip-build --root $RPM_BUILD_ROOT

%files
%doc README LICENSE
%{_bindir}/sarstats
%{python3_sitelib}/*.egg-info
%{python3_sitelib}/*.py
%{python3_sitelib}/*.py[oc]

%changelog
* Fri Dec 27 2013 Michele Baldessari <michele@acksyn.org> - 0.1-1
- Initial release
