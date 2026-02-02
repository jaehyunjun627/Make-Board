<%@page import="model.AddrDAO"%>
<%@page import="model.AddrDTO"%>
<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<link rel="stylesheet" type=" text/css" href="../css/addrlist.css" />

<title>addrlist</title>

</head>
<body>
	<jsp:useBean class="model.AddrDAO" id="am" scope="application" />

	<div class="container">
		<h2>address</h2>
		<a href="03_addr_form.jsp"></a>
		<p></p>
		<form action="sname.jsp" method="get">
			<input type="text" name="sname" placeholder="이름으로 검색" />
			<p></p>
			<input type="submit" value="검색" />
		</form>
		<p></p>
		<table border="1">

			<thead>
				<tr>
					<th>이름</th>
					<th>전화번호</th>
					<th>이메일</th>
					<th>성별</th>
				</tr>
			</thead>

			<tbody>
				<%
				for (AddrDTO ab : am.getAddrlist()) {
				%>
				<tr>
					<td><%=ab.getUsername()%></td>
					<td><%=ab.getTel()%></td>
					<td><%=ab.getEmail()%></td>
					<td><%=ab.getGender()%></td>
				</tr>
				<%
				}
				%>
			</tbody>
		</table>
	</div>

</body>
</html>