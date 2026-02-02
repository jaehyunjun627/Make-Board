<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>MemberJoinProc</title>
<link rel="stylesheet" type="text/css" href="../css/table.css" />
</head>
<body>
<%
//한글깨짐 방지
request.setCharacterEncoding("utf-8");
String id =request.getParameter("id");
String pass1 =request.getParameter("pass1");
String pass2 =request.getParameter("pass2");
String email =request.getParameter("email");
String gender =request.getParameter("gender");
String address =request.getParameter("address");
String phone =request.getParameter("phone");
String[] hobby =request.getParameterValues("hobby");
String job =request.getParameter("job");
String age =request.getParameter("age");
String info =request.getParameter("info");
%>


</body>
</html>