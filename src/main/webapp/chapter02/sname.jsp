<%@page import="model.AddrDAO"%>
<%@page import="model.AddrDTO"%>
<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<link rel="stylesheet" type=" text/css" href="../css/addrlist.css" />

<title>sname</title>
</head>
<body>
	<jsp:useBean class="model.AddrDAO" id="am" scope="application" />

	<%
	request.setCharacterEncoding("utf-8");
	String username = request.getParameter("sname");
	AddrDTO addr = am.getadd(username);
	%>
	<div class="container">
		<h2>상세 등록 내용</h2>
		<%
		if (addr != null) {
		%>
		<p>
			<strong>이름:</strong>
			<%=addr.getUsername()%></p>
		<p>
			<strong>전화번호:</strong>
			<%=addr.getTel()%></p>
		<p>
			<strong>이메일:</strong>
			<%=addr.getEmail()%></p>
		<p>
			<strong>성별:</strong>
			<%=addr.getGender()%></p>
		<%
		} else {
		%>
		<p class="message">해당 이름으로 등록된 주소가 없습니다.</p>
		<%
		}
		%>
		<hr />
		<a href="addr_list.jsp">전체 목록 보기</a>

	</div>

</body>
</html>