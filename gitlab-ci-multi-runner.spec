#
# Conditional build:
%bcond_with	bindata		# embed docker images to binary (upstream compatible)

# the revision for images
# $ git fetch https://gitlab.com/gitlab-org/gitlab-ci-multi-runner refs/tags/v1.6.0
# $ git rev-list -n 1 --abbrev-commit FETCH_HEAD
#define revision 76fdacd
# No changes to image, so don't refetch it
%define revision 1.5.2
Summary:	The official GitLab CI runner written in Go
Name:		gitlab-ci-multi-runner
Version:	1.7.1
Release:	1.1
License:	MIT
Group:		Development/Building
Source0:	https://gitlab.com/gitlab-org/gitlab-ci-multi-runner/repository/archive.tar.gz?ref=v%{version}&/%{name}-%{version}.tar.gz
# Source0-md5:	ffc78abf7e8aa4aef2778aea14d5e6a0
Source1:	https://gitlab-ci-multi-runner-downloads.s3.amazonaws.com/master/docker/prebuilt-x86_64.tar.xz
# Source1-md5:	0d89c7578a0b5d22a4ae85dcb7d5b4f5
Source2:	https://gitlab-ci-multi-runner-downloads.s3.amazonaws.com/master/docker/prebuilt-arm.tar.xz
# Source2-md5:	c0533c581624dcb33095f08f06e6a00b
Source3:	%{name}.init
Source4:	%{name}.sysconfig
Source5:	%{name}.service
Patch0:		nodim_gz.patch
Patch1:		branch-preserver.patch
URL:		https://gitlab.com/gitlab-org/gitlab-ci-multi-runner
BuildRequires:	git-core
%{?with_bindata:BuildRequires:	go-bindata >= 3.0.7-1.a0ff2567}
BuildRequires:	golang >= 1.4
BuildRequires:	rpmbuild(macros) >= 1.647
Requires(post,preun):	/sbin/chkconfig
Requires(post,preun,postun):	systemd-units >= 38
Requires(postun):	/usr/sbin/groupdel
Requires(postun):	/usr/sbin/userdel
Requires(pre):	/bin/id
Requires(pre):	/usr/bin/getgid
Requires(pre):	/usr/sbin/groupadd
Requires(pre):	/usr/sbin/useradd
Requires:	bash
Requires:	ca-certificates
Requires:	curl
Requires:	git-core
Requires:	rc-scripts
Requires:	systemd-units >= 0.38
Requires:	tar
Suggests:	docker >= 1.8
Provides:	group(gitlab-runner)
Provides:	user(gitlab-runner)
ExclusiveArch:	%{ix86} %{x8664} %{arm}
BuildRoot:	%{tmpdir}/%{name}-%{version}-root-%(id -u -n)

# go stuff
%define _enable_debug_packages 0
%define gobuild(o:) go build -ldflags "${LDFLAGS:-} -B 0x$(head -c20 /dev/urandom|od -An -tx1|tr -d ' \\n')" -a -v -x %{?**};
%define import_path	gitlab.com/gitlab-org/gitlab-ci-multi-runner

%description
This is the official GitLab Runner written in Go. It runs tests and
sends the results to GitLab. GitLab CI is the open-source continuous
integration service included with GitLab that coordinates the testing.

%prep
%setup -qc

# for doc
mv gitlab-ci-multi-runner-*/*.md .

# don't you love go?
install -d src/$(dirname %{import_path})
mv gitlab-ci-multi-runner-* src/%{import_path}
cd src/%{import_path}

%{!?with_bindata:%patch0 -p1}
%patch1 -p5

%if %{with bindata}
install -d out/docker
ln -s %{SOURCE1} out/docker
ln -s %{SOURCE2} out/docker
# touch, otherwise make rules would download it nevertheless
touch out/docker/prebuilt-*.tar.xz
%endif

# avoid docker being used even if executable found
cat <<'EOF' > docker
#!/bin/sh
echo >&2 "No docker"
exit 1
EOF
chmod a+rx docker

%build
export GOPATH=$(pwd)
cd src/%{import_path}
export PATH=$(pwd):$PATH

%if %{with bindata}
# build docker bindata. if you forget this, you get such error:
# executors/docker/executor_docker.go:180: undefined: Asset
%{__make} docker
%endif

%{__make} version | tee version.txt

CN=gitlab.com/gitlab-org/gitlab-ci-multi-runner/common
LDFLAGS="-X $CN.NAME=gitlab-ci-multi-runner -X $CN.VERSION=%{version} -X $CN.REVISION=%{revision}"
%gobuild

# verify that version matches
./gitlab-ci-multi-runner -v > v
v=$(awk '$1 == "Version:" {print $2}' v)
test "$v" = "%{version}"

%install
rm -rf $RPM_BUILD_ROOT
install -d $RPM_BUILD_ROOT{%{_sysconfdir}/gitlab-runner,%{_bindir},/etc/{rc.d/init.d,sysconfig},%{systemdunitdir},/var/lib/gitlab-runner/.gitlab-runner}

install -p src/%{import_path}/%{name} $RPM_BUILD_ROOT%{_bindir}/gitlab-runner
install -p %{SOURCE3} $RPM_BUILD_ROOT/etc/rc.d/init.d/%{name}
cp -p %{SOURCE4} $RPM_BUILD_ROOT/etc/sysconfig/%{name}
cp -p %{SOURCE5} $RPM_BUILD_ROOT%{systemdunitdir}

# backward compat name for previous pld packaging
ln -s gitlab-runner $RPM_BUILD_ROOT%{_bindir}/gitlab-ci-multi-runner

%if %{without bindata}
cp -p %{SOURCE1} $RPM_BUILD_ROOT/var/lib/gitlab-runner
cp -p %{SOURCE2} $RPM_BUILD_ROOT/var/lib/gitlab-runner
%endif

%clean
rm -rf $RPM_BUILD_ROOT

%pre
%groupadd -g 330 gitlab-runner
%useradd -u 330 -d /var/lib/gitlab-runner -g gitlab-runner -c "GitLab Runner" gitlab-runner

%postun
if [ "$1" = "0" ]; then
	%userremove gitlab-runner
	%groupremove gitlab-runner
fi
%systemd_reload

%post
/sbin/chkconfig --add %{name}
%service %{name} restart
%systemd_post %{name}.service

%preun
if [ "$1" = "0" ]; then
	%service -q %{name} stop
	/sbin/chkconfig --del %{name}
fi
%systemd_preun %{name}.service

%files
%defattr(644,root,root,755)
%doc README.md CHANGELOG.md
%config(noreplace) %verify(not md5 mtime size) /etc/sysconfig/gitlab-ci-multi-runner
%attr(754,root,root) /etc/rc.d/init.d/gitlab-ci-multi-runner
%dir %attr(750,root,root) %{_sysconfdir}/gitlab-runner
%attr(755,root,root) %{_bindir}/gitlab-ci-multi-runner
%attr(755,root,root) %{_bindir}/gitlab-runner
%{systemdunitdir}/gitlab-ci-multi-runner.service
%dir %attr(750,gitlab-runner,gitlab-runner) /var/lib/gitlab-runner
%dir %attr(750,gitlab-runner,gitlab-runner) /var/lib/gitlab-runner/.gitlab-runner

%if %{without bindata}
/var/lib/gitlab-runner/prebuilt-arm.tar.xz
/var/lib/gitlab-runner/prebuilt-x86_64.tar.xz
%endif
