<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Insert title here</title>
</head>
<body>
1.서버 정보
<%= application.getServerInfo() %> <br />
<%= application.getServerInfo() %> 	<br />
실제 경로
<% 
application.setAttribute("username", "김민석");
application.log("user login : username =김닌석");
application.log("debug 세션상태 = " + session.getAttribute("state"));

application.setAttribute("count",0);


%>

<a href="application_result.jsp">확인하기</a>

</body>
</html>